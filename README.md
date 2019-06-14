<td><a href="https://www.youtube.com/watch?v=emKcwWaTjyg" title="Youtube" rel="noopener"><img src="https://i.imgur.com/eEX1qmB.png"></a></td>

Welcome to openpilot OLD_CARS_BRANCH
======

[openpilot](http://github.com/commaai/openpilot) is an open source driving agent. Currently, it performs the functions of Adaptive Cruise Control (ACC) and Lane Keeping Assist System (LKAS).  It's about on par with Tesla Autopilot and GM Super Cruise, and better than [all other manufacturers](http://www.thedrive.com/tech/5707/the-war-for-autonomous-driving-part-iii-us-vs-germany-vs-japan).

This OLD_CAR Branch bings openpilot to almost every car. Follow this readme to get an overview how it works.

Big thank you goes to @wocsor. He developed the whole thing and modified the code.

The openpilot codebase has been written to be concise and to enable rapid prototyping. We look forward to your contributions - improving real vehicle automation has never been easier.

OVERVIEW
=======================

To make openpilot work in an old car, we neet to retrofit actuators from supported cars like toyota corolla 2018. Some small ECU needs to be build DIY.

Brain:
* [EON & Pada](#EON-&-Panda)


Steering:
* [EPS - electric power steering](#EPS)
* [VSS - vehicle speed sensor](#supported-cars)
* [Buttons](#community-maintained-cars)
* [Cruise ECU](#supported-cars)
* [Steering angle sensor](#hardware)

Throttle:
* [Cruise Control Actuator](#in-progress-cars)
* [Potentiometer](#directory-structure)
* [Throttle ECU](#how-can-i-add-support-for-my-car)

Radar: 
* [Radar sensor](#in-progress-cars)

Brake (not finished yet):
* [ABS PUMP / OSCC Module](#user-data--chffr-account--crash-reporting)

Community
 * [Community](#user-data--chffr-account--crash-reporting)

# BRAIN

## EON & Panda

![enter image description here](https://i.imgur.com/RBqQvoZ.jpg)

First, we need a brain to control everything. 
This is EON. And extremely powerful piece of hardware which runs openpitlot code. 
We also need Panda, which connects EON to the OBD2 port of the car. Now eon can talk to the car via CAN bus. 
Oh wait! - we do not have an  CAN network in our car. But don't worry we will build it our selfs.
For more informations to EON and PANDA visite [comma.ai.](https://comma.ai)

I have used a cheap [OBD2 Wire Connector](https://www.amazon.com/iKKEGOL-Connector-Diagnostic-Extension-Pigtail/dp/B07F16HC12/ref=sr_1_15?__mk_de_DE=%C3%85M%C3%85%C5%BD%C3%95%C3%91&keywords=obd2%20cable&qid=1560506720&s=gateway&sr=8-15) to pinout the panda. 


# STEERING


## EPS - eclectic power steering

We use a EPS (electronic power steering) out of a Toyota corolla 2018.
This is already supported by Openpilot so we do not have to port it from sketch.
This is the electric steering Column out of a corolla: 
![enter image description here](https://i.imgur.com/PUOQNph.png)

It is really important, that is has LKAS (lane keep assistent). Therefore make sure to buy it from 2018 corolla. The steering column and motor might be the same like in older corollas. But the ECU is different. So make sure to buy the one with "KV" on the sticker:
![enter image description here](https://i.imgur.com/Bl3FpBX.png)

This is how to wire the steering ECU:

![enter image description here](https://i.imgur.com/w6tnlDq.png)

z11 and z7 connectors goes to the EPS Motor.

Now its time to retrofit it in your car. Since every car is different, you need to be a little creative. 
Im my case, I have cut my stock column in half and welded both ends to the corolla steering column.
If you already have a hydraulic power steering, you might want to disable that. Otherwise you would have a Power steering on top of a power steering. 
This is how my conversion looks like: 

![enter image description here](https://i.imgur.com/TTxdILC.jpg)

![enter image description here](https://i.imgur.com/349kMvt.png)

Now we have a working power steering in our car! 
Unfortunately the ECU goes into failsafe, which means that it will disable LKAS. 
We will solve this issue later with our Cruise ECU.

----
**VSS - vehicle speed sensor**

Eon needs to know how fast we are driving. Therefore we need to add sensor which measure the speed of the car. Most cars already provide such a signal already. For example for the radio. If you have such a signal, you can grab that. In my case I have added a hall sensor to the rotary disc of the speedometer. This counts 4000 signal each km. With that sensor, we can calculate the speed in Cruise ECU and send it to EON via can. 


----
**Buttons**

Since we do not have original toyota buttons, - guess what - we need to build it our selfs.
Be creative, its quite simple. Pull-down buttons, which we will connect to  Cruise ECU later. 

![enter image description here](https://i.imgur.com/V3gqlWY.png)

![enter image description here](https://i.imgur.com/LdcZqPN.jpg)

----
**Cruise ECU**

Cruise ECU is build out of an [Arduino Uno](https://www.amazon.com/Elegoo-EL-CB-001-ATmega328P-ATMEGA16U2-Arduino/dp/B01EWOE0UU/ref=sr_1_2?__mk_de_DE=%C3%85M%C3%85%C5%BD%C3%95%C3%91&keywords=arduino%20uno&qid=1560514638&s=gateway&sr=8-2) with a [CAN bus shield](https://www.amazon.com/MakerFocus-CAN-Bus-Shield-V1-2/dp/B06XWQ4WF9/ref=sr_1_2?__mk_de_DE=%C3%85M%C3%85%C5%BD%C3%95%C3%91&keywords=arduino%20uno%20canbus%20shield&qid=1560514663&s=gateway&sr=8-2) attached.
![enter image description here](https://i.imgur.com/CnysIXP.png)


It handles the following functions: 

 1. Cruise_ECU sends some CAN messages on the bus, which let the EPS Ecu thinks its still in a corolla. The EPS is happy and does not go into failsafe. LKAS is ready to take control of it !!! 
 
 2. Cruise_ECU calculates the current speed by reading the VSS. It sends a 0xb4 and 0xaa message on the can  bus.  EON and Cruise_ECU can read those messages.
 
 3. Cruise_ECU digitalReads the Buttons and sends the right messages to the CAN Bus. This lets us enable/disable, increase or decrease set speed.
 
 5. It also provide some safety function. It will disable  immediately, if it looses CAN connection. 
 
 This is how you wire Cruise_ECU: 
![CRUISE_ECU_PINOUT](https://i.imgur.com/9Mnr5qg.jpg)

Note: The LED stuff is optional. "Interrupt to throttle ecu" is an extra safety feature, not necessary but recommended. 

[Download Cruise ECU Code.](https://github.com/Lukilink/Cruise_ECU)


----
**Steering angle sensor**

The steering angle sensor is the last missing piece. 
I am using the sensor out of a toyota corolla / rav4.
I would recommend buying it with the spring attached. Also we do not need the hair spring, it takes care of the sensor while shipping. If the sensor rotate to much it will be damaged. 
Fortunatley the sensor provides it's own ECU. Therefor is is like plug and pay. 

![enter image description here](https://i.imgur.com/8hsyrax.png)


![enter image description here](https://i.imgur.com/CwXuUUv.jpg)
	
The stock Toyota sensor is laggy and not precise. 
Zorrobyte has started to build a high precision, fast like hell, sensor. 
Check out his [Github](https://github.com/zorrobyte/betterToyotaAngleSensorForOP). 
I will defenetley upgrade to his sensor.

---

# THROTTLE

**Cruise Control Actuator**

Add an electric cruise control actuator to your throttle.
Chose what ever brand you like. They are all very similar. 
It should have an electric motor in it, and something like a clutch.
There is a solenoid in it, which disconnects everything mechanically. Pretty safe :) 
If you already have stock cruise control in your car. Use that one! 

**Potentiometer**

To measure the position of the throttle we use the stock potentiometer. Almost every throttle has a potentiometer attached. 

**Throttle ECU**

Throttle ECU Hardware is an [Arduino Uno](https://www.amazon.com/Elegoo-EL-CB-001-ATmega328P-ATMEGA16U2-Arduino/dp/B01EWOE0UU/ref=sr_1_3?__mk_de_DE=%C3%85M%C3%85%C5%BD%C3%95%C3%91&keywords=arduino%20uno&qid=1560516407&s=gateway&sr=8-3) with a [CAN-bus shield](https://www.amazon.com/MakerFocus-CAN-Bus-Shield-V1-2/dp/B06XWQ4WF9/ref=sr_1_2?__mk_de_DE=%C3%85M%C3%85%C5%BD%C3%95%C3%91&keywords=arduino%20uno%20canbus%20shield&qid=1560514663&s=gateway&sr=8-2) and a [H-bridge](https://www.amazon.com/CJRSLRB-3Packs-Controller-H-Bridge-Arduino/dp/B07BMTQMKN/ref=sr_1_2_sspa?__mk_de_DE=%C3%85M%C3%85%C5%BD%C3%95%C3%91&keywords=H-bridge&qid=1560516427&s=gateway&sr=8-2-spons&psc=1) attached.

![enter image description here](https://i.imgur.com/EClutor.png)

It handles the following functions: 

 1. Throttle_ECU transmits the angle_requests from EON and runs the cruise actuator motor and solenoid.
 
 2. It calculates the acceleration amount depending on the current speed. That means it accelerate faster when driving fast, and more smooth and carefully when driving slow. 
 
 4. It provide some safety function. It will disengage immediately, if it looses can messages. 

Download [Throttle_ECU Code](https://github.com/Lukilink/Cruise_ECU).

![enter image description here](https://i.imgur.com/FgJhgx8.png)

---
# RADAR

**RADAR**


![enter image description here](https://i.imgur.com/0dD9zPy.png)

Similar to the steering angle sensor, the radar out of a corolla / rav4 provides its own ECU. 
Therefore it is pretty easy to install. 

![enter image description here](https://i.imgur.com/soMhXAJ.png)

Make sure, to fingerprint after you have installed. 

---

# BRAKE

Brake is not finished at the moment. Therefore I will not go to much in detail. 
There are different options on that at the moment. 

**POLYSYNC OSCC Brake module and Prius Actuator**

![enter image description here](https://i.imgur.com/fcA75LR.png)

[Polysync /oscc](https://github.com/PolySync/oscc) has build a board with an Arduino mega to control a toyota prius ABS actuator. 

This actuator will be placed on top of the brake system in our car. 

To do:  merge / port the OSCC DBC to openpilot

[ossc.dbc](https://github.com/PolySync/oscc/blob/master/api/include/can_protocols/oscc.dbc)
I would appreciate if someone could help us with that. 

---

# COMMUITY

Community is the most important thing in this project.



Comma [Twitter you should follow](https://twitter.com/comma_ai).

Also, we have a several thousand people community on [Discord](https://discord.comma.ai).


Licensing
------

openpilot is released under the MIT license. Some parts of the software are released under other licenses as specified.

Any user of this software shall indemnify and hold harmless Comma.ai, Inc. and its directors, officers, employees, agents, stockholders, affiliates, subcontractors and customers from and against all allegations, claims, actions, suits, demands, damages, liabilities, obligations, losses, settlements, judgments, costs and expenses (including without limitation attorneys’ fees and costs) which arise out of, relate to or result from any use of this software by user.

**THIS IS ALPHA QUALITY SOFTWARE FOR RESEARCH PURPOSES ONLY. THIS IS NOT A PRODUCT.
YOU ARE RESPONSIBLE FOR COMPLYING WITH LOCAL LAWS AND REGULATIONS.
NO WARRANTY EXPRESSED OR IMPLIED.**

---

<img src="https://d1qb2nb5cznatu.cloudfront.net/startups/i/1061157-bc7e9bf3b246ece7322e6ffe653f6af8-medium_jpg.jpg?buster=1458363130" width="75"></img> <img src="https://cdn-images-1.medium.com/max/1600/1*C87EjxGeMPrkTuVRVWVg4w.png" width="225"></img>
