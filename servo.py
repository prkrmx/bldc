#!/usr/bin/python

import sys
from time import sleep
import pigpio
from read_RPM import reader

# Connect to pigpio
pi = pigpio.pi()

if not pi.connected:
    exit(0)

# Calibrate ESC
ESC_GPIO = 13
pi.set_servo_pulsewidth(ESC_GPIO, 0)
sleep(.5)
pi.set_servo_pulsewidth(ESC_GPIO, 500)
sleep(.5)


# pi.set_servo_pulsewidth(ESC_GPIO, 2500) # Maximum throttle.
# sleep(2)
# pi.set_servo_pulsewidth(ESC_GPIO, 500) # Minimum throttle.
# sleep(2)


# Set up RPM reader
RPM_GPIO = 14
tach = reader(pi, RPM_GPIO)

SAMPLE_TIME = 1.0

while True:
    try:
        speed = 0

        # Set ESC speed via PWM
        pi.set_servo_pulsewidth(ESC_GPIO, speed * 1000 / 7 + 1000)

        # Read RPM
        rpm = tach.RPM()
        print("RPM\t{:.0f}".format(rpm))

        sleep(SAMPLE_TIME)
    except KeyboardInterrupt:
        print("\nExit")
        pi.set_servo_pulsewidth(ESC_GPIO, 0)  # Stop servo pulses.
        pi.stop()  # Disconnect pigpio.
        sys.exit()
