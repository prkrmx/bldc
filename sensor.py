#!/usr/bin/env python

import sys
from time import sleep
import pigpio

pi = pigpio.pi()

if not pi.connected:
    exit(0)

sensor = pi.spi_open(0, 900000, 3)
while True:
    try:
        c, d = pi.spi_read(sensor, 2)
        if c == 2:
            word = (d[0] << 8) | d[1]
            t = (word >> 5)
            if (word & 0x18) == 0:
                # t = (word >> 5)/2.8495
                print("{:b}\t{:.2f}".format(word, t))
            else:
                print("{:b}\t{:.2f} BAD READING!!!!".format(word, t))

        # c, d = pi.spi_read(sensor, 1)
        # c, dd = pi.spi_read(sensor, 1)
        # if c == 1:
        #     word = (d[0] << 8) | dd[0]
        #     t = (word >> 5)
        #     if (word & 0x18) == 0:
        #         # t = (word >> 5)/2.8495
        #         print("{:b}\t{:.2f}".format(word, t))
        #     else:
        #         print("{:b}\t{:.2f} BAD READING!!!!".format(word, t))
        sleep(.25)
    except KeyboardInterrupt:
        print("\nExit")
        pi.spi_close(sensor)
        pi.stop()
        sys.exit()