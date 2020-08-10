#!/usr/bin/env python

import sys
from time import sleep
import pigpio

pi = pigpio.pi()

if not pi.connected:
    print("GPIO not connected")
    exit(0)

sensor = pi.spi_open(0, 1000000, 1)
trimmer = pi.spi_open(1, 1000000, 3)

data = 0




while True:
    try:

        c, d = pi.spi_read(sensor, 2)
        if c == 2:
            word = (d[0] << 8) | d[1]
            t = (word >> 6)/2.8495
            if (word & 0x38) == 0x20:
                print("{:b}\t{:.2f}".format(word, t))
            else:
                print("{:b}\t{:.2f} BAD READING!!!!".format(word, t))
        
        data += 10
        if data == 250:
            data = 240

        # data = 255
        cmd = 0x11

        # print("WRITE: {:d}".format(data))
        # pi.spi_xfer(trimmer, data)
        pi.spi_write(trimmer, [cmd, data])

        sleep(.001)
    except KeyboardInterrupt:
        print("\nExit")
        pi.spi_write(trimmer, [cmd, 0])
        pi.spi_close(trimmer)
        pi.spi_close(sensor)
        pi.stop()
        sys.exit()