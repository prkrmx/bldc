#!/usr/bin/env python

import sys
from time import sleep
import pigpio

pi = pigpio.pi()

if not pi.connected:
    print("GPIO not connected")
    exit(0)

sensor = pi.spi_open(1, 1000000, 3)
data = 0




while True:
    try:
        data += 10
        if data == 250:
            data = 240


        # data = 255
        cmd = 0x11

        print("WRITE: {:d}".format(data))
        # pi.spi_xfer(sensor, data)
        pi.spi_write(sensor, [cmd, data])

        sleep(.50)
    except KeyboardInterrupt:
        print("\nExit")
        pi.spi_write(sensor, [cmd, 0])
        pi.spi_close(sensor)
        pi.stop()
        sys.exit()
