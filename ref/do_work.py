#!/usr/bin/env python

import sys
from time import sleep
import pigpio

pi = pigpio.pi()

if not pi.connected:
    print("GPIO not connected")
    exit(0)


PWM = 13
DIR = 19
BR = 26
pi.set_PWM_frequency(PWM, 100000)
pi.set_PWM_dutycycle(PWM, 0)

pi.set_mode(DIR, pigpio.OUTPUT)
pi.set_mode(BR, pigpio.OUTPUT)

pi.write(DIR, 1)       # 1-CW 0-CCW
pi.write(BR, 0)

sensor = pi.spi_open(0, 1000000, 1)
trimmer = pi.spi_open(1, 1000000, 3)

data = 10

TRIM_EN = 12    # GPIO12
pi.set_mode(TRIM_EN, pigpio.OUTPUT)
pi.write(TRIM_EN, 1)

cmd = 0x11
while True:
    try:

        c, d = pi.spi_read(sensor, 2)
        if c == 2:
            word = (d[0] << 8) | d[1]

            t = (word >> 6)#/2.8495
            if (word & 0x38) == 0x20:
                # print("{:.2f}\t{:b}".format(t,word))
                print("{:d}\t{:b}".format(t,word))
                if t == 0:
                    print("-------------------------")
                    pi.spi_write(trimmer, [cmd, 0])
                    pi.write(TRIM_EN, 0)
                    pi.write(BR, 1)
                    pi.set_PWM_dutycycle(PWM, 0)
                    pi.spi_close(trimmer)
                    pi.spi_close(sensor)
                    pi.stop()
                    sys.exit()
            else:
                # print("{:.2f}\t{:b} BAD READING!!!!".format(t,word))
                print("{:d}\t{:b} BAD READING!!!!".format(t,word))
        
        pi.set_PWM_dutycycle(PWM, 64)


        # data = 255
        

        # print("WRITE: {:d}".format(data))
        # pi.spi_xfer(trimmer, data)
        pi.spi_write(trimmer, [cmd, data])

        sleep(.005)
    except KeyboardInterrupt:
        print("\nExit")
        pi.spi_write(trimmer, [cmd, 0])
        pi.write(TRIM_EN, 0)
        pi.write(BR, 1)
        pi.set_PWM_dutycycle(PWM, 0)
        pi.spi_close(trimmer)
        pi.spi_close(sensor)
        pi.stop()
        sys.exit()