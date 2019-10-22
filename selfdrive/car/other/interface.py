#!/usr/bin/env python3
from cereal import car
from selfdrive.config import Conversions as CV
from selfdrive.controls.lib.drive_helpers import EventTypes as ET, create_event
from selfdrive.controls.lib.vehicle_model import VehicleModel
from selfdrive.car.other.carstate import CarState, get_can_parser, get_cam_can_parser
from selfdrive.car.other.values import ECU, ECU_FINGERPRINT, CAR, NO_STOP_TIMER_CAR, TSS2_CAR, FINGERPRINTS
from selfdrive.car import STD_CARGO_KG, scale_rot_inertia, scale_tire_stiffness, is_ecu_disconnected, gen_empty_fingerprint
from selfdrive.swaglog import cloudlog
from selfdrive.car.interfaces import CarInterfaceBase

ButtonType = car.CarState.ButtonEvent.Type
GearShifter = car.CarState.GearShifter

class CarInterface(CarInterfaceBase):
  def __init__(self, CP, CarController):
    self.CP = CP
    self.VM = VehicleModel(CP)

    self.frame = 0
    self.gas_pressed_prev = False
    self.brake_pressed_prev = False
    self.cruise_enabled_prev = False

    # *** init the major players ***
    self.CS = CarState(CP)

    self.cp = get_can_parser(CP)
    self.cp_cam = get_cam_can_parser(CP)

    self.forwarding_camera = False

    self.CC = None
    if CarController is not None:
      self.CC = CarController(self.cp.dbc_name, CP.carFingerprint, CP.enableCamera, CP.enableDsu, CP.enableApgs)

  @staticmethod
  def compute_gb(accel, speed):
    return float(accel) / 3.0

  @staticmethod
  def get_params(candidate, fingerprint=gen_empty_fingerprint(), vin="", has_relay=False):

    ret = car.CarParams.new_message()

    ret.carName = "other"
    ret.carFingerprint = candidate
    ret.carVin = vin
    ret.isPandaBlack = has_relay

    ret.safetyModel = car.CarParams.SafetyModel.toyota

    # pedal
    ret.enableCruise = not ret.enableGasInterceptor

    ret.steerActuatorDelay = 0.12  # Default delay, Prius has larger delay

    if candidate not in [CAR.OLD_CAR]: # These cars use LQR/INDI
      ret.lateralTuning.init('pid')
      ret.lateralTuning.pid.kiBP, ret.lateralTuning.pid.kpBP = [[0.], [0.]]

    if candidate == CAR.OLD_CAR:
      stop_and_go = True
      ret.safetyParam = 100
      ret.wheelbase = 2.455
      ret.steerRatio = 17.
      tire_stiffness_factor = 0.444
      ret.mass = 6200.0 * CV.LB_TO_KG + STD_CARGO_KG
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.1], [0.04]]
      ret.lateralTuning.pid.kf = 0.00004
      ret.lateralTuning.init('lqr')

      ret.lateralTuning.lqr.scale = 1500.0
      ret.lateralTuning.lqr.ki = 0.05

      ret.lateralTuning.lqr.a = [0., 1., -0.22619643, 1.21822268]
      ret.lateralTuning.lqr.b = [-1.92006585e-04, 3.95603032e-05]
      ret.lateralTuning.lqr.c = [1., 0.]
      ret.lateralTuning.lqr.k = [-110.73572306, 451.22718255]
      ret.lateralTuning.lqr.l = [0.3233671, 0.3185757]
      ret.lateralTuning.lqr.dcGain = 0.002237852961363602

    ret.steerRateCost = 1.
    ret.centerToFront = ret.wheelbase * 0.5

    # TODO: get actual value, for now starting with reasonable value for
    # civic and scaling by mass and wheelbase
    ret.rotationalInertia = scale_rot_inertia(ret.mass, ret.wheelbase)

    # TODO: start from empirically derived lateral slip stiffness for the civic and scale by
    # mass and CG position, so all cars will have approximately similar dyn behaviors
    ret.tireStiffnessFront, ret.tireStiffnessRear = scale_tire_stiffness(ret.mass, ret.wheelbase, ret.centerToFront,
                                                                         tire_stiffness_factor=tire_stiffness_factor)

    # no rear steering, at least on the listed cars above
    ret.steerRatioRear = 0.
    ret.steerControlType = car.CarParams.SteerControlType.torque

    # steer, gas, brake limitations VS speed
    ret.steerMaxBP = [16. * CV.KPH_TO_MS, 45. * CV.KPH_TO_MS]  # breakpoints at 1 and 40 kph
    ret.steerMaxV = [1., 1.]  # 2/3rd torque allowed above 45 kph
    ret.brakeMaxBP = [0.]
    ret.brakeMaxV = [1.]

    ret.enableCamera = is_ecu_disconnected(fingerprint[0], FINGERPRINTS, ECU_FINGERPRINT, candidate, ECU.CAM) or has_relay
    ret.enableDsu = is_ecu_disconnected(fingerprint[0], FINGERPRINTS, ECU_FINGERPRINT, candidate, ECU.DSU) or (has_relay and candidate in TSS2_CAR)
    ret.enableApgs = False  # is_ecu_disconnected(fingerprint[0], FINGERPRINTS, ECU_FINGERPRINT, candidate, ECU.APGS)
    ret.enableGasInterceptor = 0x201 in fingerprint[0]
    ret.openpilotLongitudinalControl = ret.enableCamera and ret.enableDsu
    cloudlog.warning("ECU Camera Simulated: %r", ret.enableCamera)
    cloudlog.warning("ECU DSU Simulated: %r", ret.enableDsu)
    cloudlog.warning("ECU APGS Simulated: %r", ret.enableApgs)
    cloudlog.warning("ECU Gas Interceptor: %r", ret.enableGasInterceptor)

    # min speed to enable ACC. if car can do stop and go, then set enabling speed
    # to a negative value, so it won't matter.
    ret.minEnableSpeed = -1. if (stop_and_go or ret.enableGasInterceptor) else 19. * CV.MPH_TO_MS

    ret.steerLimitAlert = False

    ret.longitudinalTuning.deadzoneBP = [0., 9.]
    ret.longitudinalTuning.deadzoneV = [0., .15]
    ret.longitudinalTuning.kpBP = [0., 5., 35.]
    ret.longitudinalTuning.kiBP = [0., 35.]
    ret.stoppingControl = False
    ret.startAccel = 0.0

    if ret.enableGasInterceptor:
      ret.gasMaxBP = [0., 9., 35]
      ret.gasMaxV = [0.2, 0.5, 0.7]
      ret.longitudinalTuning.kpV = [1.2, 0.8, 0.5]
      ret.longitudinalTuning.kiV = [0.18, 0.12]
    else:
      ret.gasMaxBP = [0.]
      ret.gasMaxV = [0.5]
      ret.longitudinalTuning.kpV = [3.6, 2.4, 1.5]
      ret.longitudinalTuning.kiV = [0.54, 0.36]

    return ret

  # returns a car.CarState
  def update(self, c, can_strings):
    # ******************* do can recv *******************
    self.cp.update_strings(can_strings)
    self.cp_cam.update_strings(can_strings)

    self.CS.update(self.cp)

    # create message
    ret = car.CarState.new_message()

    ret.canValid = self.cp.can_valid

    # speeds
    ret.vEgo = self.CS.v_ego
    ret.vEgoRaw = self.CS.v_ego_raw
    ret.aEgo = self.CS.a_ego
    ret.yawRate = self.VM.yaw_rate(self.CS.angle_steers * CV.DEG_TO_RAD, self.CS.v_ego)
    ret.standstill = self.CS.standstill
    ret.wheelSpeeds.fl = self.CS.v_wheel_fl
    ret.wheelSpeeds.fr = self.CS.v_wheel_fr
    ret.wheelSpeeds.rl = self.CS.v_wheel_rl
    ret.wheelSpeeds.rr = self.CS.v_wheel_rr

    # gear shifter
    ret.gearShifter = self.CS.gear_shifter

    # gas pedal
    ret.gas = self.CS.car_gas
    if self.CP.enableGasInterceptor:
    # use interceptor values to disengage on pedal press
      ret.gasPressed = self.CS.pedal_gas > 15
    else:
      ret.gasPressed = self.CS.pedal_gas > 0

    # brake pedal
    ret.brake = self.CS.user_brake
    ret.brakePressed = self.CS.brake_pressed != 0
    ret.brakeLights = self.CS.brake_lights

    # steering wheel
    ret.steeringAngle = self.CS.angle_steers
    ret.steeringRate = self.CS.angle_steers_rate

    ret.steeringTorque = self.CS.steer_torque_driver
    ret.steeringTorqueEps = self.CS.steer_torque_motor
    ret.steeringPressed = self.CS.steer_override

    # cruise state
    ret.cruiseState.enabled = self.CS.pcm_acc_active
    ret.cruiseState.speed = self.CS.v_cruise_pcm * CV.KPH_TO_MS
    ret.cruiseState.available = bool(self.CS.main_on)
    ret.cruiseState.speedOffset = 0.

    if self.CP.carFingerprint in NO_STOP_TIMER_CAR or self.CP.enableGasInterceptor:
      # ignore standstill in hybrid vehicles, since pcm allows to restart without
      # receiving any special command
      # also if interceptor is detected
      ret.cruiseState.standstill = False
    else:
      ret.cruiseState.standstill = self.CS.pcm_acc_status == 7

    buttonEvents = []
    if self.CS.left_blinker_on != self.CS.prev_left_blinker_on:
      be = car.CarState.ButtonEvent.new_message()
      be.type = ButtonType.leftBlinker
      be.pressed = self.CS.left_blinker_on != 0
      buttonEvents.append(be)

    if self.CS.right_blinker_on != self.CS.prev_right_blinker_on:
      be = car.CarState.ButtonEvent.new_message()
      be.type = ButtonType.rightBlinker
      be.pressed = self.CS.right_blinker_on != 0
      buttonEvents.append(be)

    ret.buttonEvents = buttonEvents
    ret.leftBlinker = bool(self.CS.left_blinker_on)
    ret.rightBlinker = bool(self.CS.right_blinker_on)

    ret.doorOpen = not self.CS.door_all_closed
    ret.seatbeltUnlatched = not self.CS.seatbelt

    ret.genericToggle = self.CS.generic_toggle

    # events
    events = []
    if self.cp_cam.can_valid:
      self.forwarding_camera = True

    if self.cp_cam.can_invalid_cnt >= 100 and self.CP.enableCamera:
      events.append(create_event('invalidGiraffeToyota', [ET.PERMANENT]))
    if not ret.gearShifter == GearShifter.drive and self.CP.enableDsu:
      events.append(create_event('wrongGear', [ET.NO_ENTRY, ET.SOFT_DISABLE]))
    if ret.doorOpen:
      events.append(create_event('doorOpen', [ET.NO_ENTRY, ET.SOFT_DISABLE]))
    if ret.seatbeltUnlatched:
      events.append(create_event('seatbeltNotLatched', [ET.NO_ENTRY, ET.SOFT_DISABLE]))
    if self.CS.esp_disabled and self.CP.enableDsu:
      events.append(create_event('espDisabled', [ET.NO_ENTRY, ET.SOFT_DISABLE]))
    if not self.CS.main_on and self.CP.enableDsu:
      events.append(create_event('wrongCarMode', [ET.NO_ENTRY, ET.USER_DISABLE]))
    if ret.gearShifter == GearShifter.reverse and self.CP.enableDsu:
      events.append(create_event('reverseGear', [ET.NO_ENTRY, ET.IMMEDIATE_DISABLE]))
    if self.CS.steer_error:
      events.append(create_event('steerTempUnavailable', [ET.NO_ENTRY, ET.WARNING]))
    if self.CS.low_speed_lockout and self.CP.enableDsu:
      events.append(create_event('lowSpeedLockout', [ET.NO_ENTRY, ET.PERMANENT]))
    if ret.vEgo < self.CP.minEnableSpeed and self.CP.enableDsu:
      events.append(create_event('speedTooLow', [ET.NO_ENTRY]))
      if c.actuators.gas > 0.1:
        # some margin on the actuator to not false trigger cancellation while stopping
        events.append(create_event('speedTooLow', [ET.IMMEDIATE_DISABLE]))
      if ret.vEgo < 0.001:
        # while in standstill, send a user alert
        events.append(create_event('manualRestart', [ET.WARNING]))

    # enable request in prius is simple, as we activate when Toyota is active (rising edge)
    if ret.cruiseState.enabled and not self.cruise_enabled_prev:
      events.append(create_event('pcmEnable', [ET.ENABLE]))
    elif not ret.cruiseState.enabled:
      events.append(create_event('pcmDisable', [ET.USER_DISABLE]))

    # disable on pedals rising edge or when brake is pressed and speed isn't zero
    if (ret.gasPressed and not self.gas_pressed_prev) or \
       (ret.brakePressed and (not self.brake_pressed_prev or ret.vEgo > 0.001)):
      events.append(create_event('pedalPressed', [ET.NO_ENTRY, ET.USER_DISABLE]))

    if ret.gasPressed:
      events.append(create_event('pedalPressed', [ET.PRE_ENABLE]))

    ret.events = events

    self.gas_pressed_prev = ret.gasPressed
    self.brake_pressed_prev = ret.brakePressed
    self.cruise_enabled_prev = ret.cruiseState.enabled

    return ret.as_reader()

  # pass in a car.CarControl
  # to be called @ 100hz
  def apply(self, c):

    can_sends = self.CC.update(c.enabled, self.CS, self.frame,
                               c.actuators, c.cruiseControl.cancel, c.hudControl.visualAlert,
                               self.forwarding_camera, c.hudControl.leftLaneVisible,
                               c.hudControl.rightLaneVisible, c.hudControl.leadVisible,
                               c.hudControl.leftLaneDepart, c.hudControl.rightLaneDepart)

    self.frame += 1
    return can_sends
