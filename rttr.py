#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Rotator control"""

import sys
import logging
import subprocess
import pigpio
import math

from socket import *
from time import sleep
from optparse import OptionParser
from multiprocessing import Process, Value
from read_RPM import reader


def chks(data):
    chks = 0
    for index in range(1, len(data) - 1):
        chks += data[index]
    return chks % 256


def parity(num):
    result = 0
    while num:
        result ^= num & 1
        num >>= 1
    return result


def argument_parser():
    parser = OptionParser(usage="\nsudo ./rttr.py -l 50007 -p 50008 -v\n"
                          "sudo ./rttr.py -k\n"
                          "sudo tail -f /var/log/rttr.log <-- LOGGING FILE")
    parser.add_option("-l", dest="lstr", type="int",
                      default="50007", help="Commands listener port [default=%default]")
    parser.add_option("-p", dest="port", type="int",
                      default="50008", help="Broadcast port [default=%default]")
    parser.add_option("-a", dest="addr", default="10.255.255.255",
                      help="Broadcast address [default=%default]")
    parser.add_option("-s", dest="shift", type="int", default="7",
                      help="Goto shift [default=%default]")
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                      help="If set, verbose information is printed")
    parser.add_option("-k", "--kill", action="store_true",
                      default=False, help="Kill all rttr processes")
    return parser


def kill_exit():
    # sudo kill -9 $(ps ax | grep rttr.py | grep -v "grep" | awk '{print $1}')
    logging.info("Kill all rttr processes!")
    subprocess.Popen(
        'sudo kill -9 $(ps ax | grep rttr.py | grep -v "grep" | awk \'{print $1}\')',
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.info("Exit")
    sys.exit(0)


def sensors(options, position, speed):
    logging.info("Set Broadcast socket %s@%d" % (options.addr, options.port))
    bcast_sock = socket(AF_INET, SOCK_DGRAM)
    bcast_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    bcast_sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    logging.info("Connected GPIO")
    pi_enc = pigpio.pi()

    logging.info("Open encoder SPI")
    encoder = pi_enc.spi_open(0, 1000000, 3)

    RPM_GPIO = 6
    logging.info("Set up RPM reader: GPIO %d" % (RPM_GPIO))
    tach = reader(pi_enc, RPM_GPIO, 2125, 0.5, 0.5)

    prev_pos = -1
    try:
        while True:
            # Read RPM
            rpm_f = tach.RPM()
            # if options.verbose:
            #     print("RPM {:.2f}".format(rpm_f))

            # Read position
            c, d = pi_enc.spi_read(encoder, 3)
            if c == 3:
                # word = (d[0] << 8) | d[1]
                word = ((d[0] << 16) | (d[1] << 8) | d[2]) >> 7
                # print("{:b}".format(word))
                pos_f = (word >> 6)*360/1024
                bit_parity = parity(word >> 1)
                if ((word & 0x38) == 0x20) and ((word & 0x01) == bit_parity):
                    # pos_i = round(pos_f)
                    # rpm_i = round(rpm_f)
                    pos_i = math.floor(pos_f)
                    rpm_i = math.floor(rpm_f)
                    # if options.verbose:
                    #     print("RPM {:.2f}\t POS:{:.2f}\t{:b}".format(
                    #         rpm_f, pos_f, word))
                    if prev_pos != pos_i:
                    # if pos_i > prev_pos:
                        if pos_i == 360:
                            pos_i = 0
                        prev_pos = pos_i
                        key = bytes([0xFF]) + rpm_i.to_bytes(1, 'big') + \
                            pos_i.to_bytes(2, 'big')
                        key += chks(key + bytes([0x00])).to_bytes(1, 'big')
                        bcast_sock.sendto(key, (options.addr, options.port))
                        if options.verbose:
                            print("RPM {:d}\t POS:{:d}\t{:b}".format(rpm_i, pos_i, word))
                    position.value = pos_i
                    speed.value = rpm_i
                # else:
                #     if options.verbose:
                #         print("RPM {:.2f}\t POS:{:.2f}\t{:b} BAD READING!!!!".format(
                #             rpm_f, pos_f, word))

            sleep(.001)
    except:
        bcast_sock.close()
        tach.cancel()
        pi_enc.spi_close(encoder)
        pi_enc.stop()
        logging.error("Oops! %s occurred." % (sys.exc_info()[0]))


def main(options=None):
    speed = 0   # start from this point
    try:
        if options is None:
            (options, args) = argument_parser().parse_args()

        logging.basicConfig(filename='/var/log/rttr.log',
                            format='%(asctime)s\t%(process)d\t%(levelname)s\t%(message)s', level=logging.INFO)

        if options.kill:
            kill_exit()

        logging.info("Starting GPIO daemonn")
        subprocess.Popen(['sudo pigpiod'], shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
        sleep(.2)

        logging.info("Connected GPIO")
        pi = pigpio.pi()

        if not pi.connected:
            logging.error("GPIO not connected! Exit!")
            exit(0)

        abs_poss = Value('i', 0)
        abs_speed = Value('i', 0)
        p = Process(target=sensors, args=(options, abs_poss, abs_speed))
        p.start()

        PWM = 13
        DIR = 19
        BRAKE = 26
        logging.info("Set PMW frequency & dutycycle")
        pi.set_PWM_frequency(PWM, 100000)
        pi.set_PWM_dutycycle(PWM, 0)

        logging.info("Set GPIO mode")
        pi.set_mode(DIR, pigpio.OUTPUT)
        pi.set_mode(BRAKE, pigpio.OUTPUT)

        logging.info("Set direction & brake")
        pi.write(DIR, 1)    # 1-CW 0-CCW
        pi.write(BRAKE, 1)  # 0-run 1-stop

        logging.info("Open Commands listener port: %d" % (options.lstr))
        cmd_sock = socket(AF_INET, SOCK_STREAM)
        cmd_sock.bind(('', options.lstr))
        cmd_sock.listen(1)
        conn, addr = cmd_sock.accept()

        while True:
            try:
                data = conn.recv(16)
                if not data:
                    conn, addr = cmd_sock.accept()

                if len(data) > 7:

                    cksm = chks(data)
                    apos = abs_poss.value.to_bytes(2, 'big')
                    dddddd = abs_speed.value.to_bytes(2, 'big')

                    fbk = bytearray(8)
                    fbk[0] = 0xFF
                    fbk[1] = data[1]
                    fbk[2] = data[2]
                    fbk[3] = apos[0]
                    fbk[4] = apos[1]
                    fbk[5] = dddddd[1]
                    fbk[7] = chks(fbk)
                    conn.send(fbk)
                    

                    if cksm == data[7]:
                        cmd = (data[1] << 8) | data[2]
                        # * Start
                        if cmd == 0x0102:
                            rpm = data[3]
                            acc = data[4]
                            spin = data[5]

                            log = "HOST:%s\tCMD:Start\tRPM:%d\tACC:%d\tDIR:%s" % (
                                addr[0], rpm, acc, "CW" if spin else "CCW")
                            logging.info(log)
                            if options.verbose:
                                print(log)

                            if pi.read(BRAKE):
                                logging.info("Disable safety break")
                                pi.write(BRAKE, 0)

                            logging.info("Setting direction")
                            pi.write(DIR, spin)

                            max_speed = int(rpm*23.18)
                            logging.info(
                                "Setting speed to %d. Start rotator" % (max_speed))
                            while speed < max_speed:
                                pi.set_PWM_dutycycle(PWM, speed)
                                speed += 5
                                sleep(1/acc)
                        # * GoTo
                        elif cmd == 0x0408:
                            rpm = data[3]
                            acc = data[4]
                            pos = (data[5] << 8) | data[6]
                            log = "HOST:%s\tCMD:GoTo\tRPM:%d\tACC:%d\tPOS:%d" % (
                                addr[0], rpm, acc, pos)
                            logging.info(log)
                            if options.verbose:
                                print(log)

                            if pi.read(BRAKE):
                                logging.info("Disable safety break")
                                pi.write(BRAKE, 0)

                            logging.info(
                                "Setting speed to 2.5 RPM. Start rotator")
                            while True:
                                if (speed > 70):
                                    speed -= 5
                                elif (speed < 65):
                                    speed += 5
                                else:
                                    break
                                pi.set_PWM_dutycycle(PWM, speed)
                                sleep(.1)

                            logging.info("Waiting for the required position")
                            while (pos-options.shift) % 360 != abs_poss.value:
                                sleep(.001)

                            logging.info("Stop rotator")
                            while speed > 0:
                                speed -= 5
                                pi.set_PWM_dutycycle(PWM, speed)
                                sleep(.1)
                            logging.info("Enable safety break")
                            pi.write(BRAKE, 1)
                        # * Update
                        elif cmd == 0x0810:
                            rpm = data[3]
                            acc = data[4]
                            log = "HOST:%s\tCMD:Update\tRPM:%d" % (
                                addr[0], rpm)
                            logging.info(log)
                            if options.verbose:
                                print(log)

                            if pi.read(BRAKE):
                                logging.info(
                                    "The rotator does not move! Nothing to do")
                            else:
                                max_speed = int(rpm*23.18)
                                if max_speed > speed:
                                    logging.info(
                                        "Increase speed to %d." % (max_speed))
                                    while speed < max_speed:
                                        pi.set_PWM_dutycycle(PWM, speed)
                                        speed += 5
                                        sleep(0.1)
                                else:
                                    logging.info(
                                        "Reducing speed to %d." % (max_speed))
                                    while speed > max_speed:
                                        speed -= 5
                                        pi.set_PWM_dutycycle(PWM, speed)
                                        sleep(0.1)
                        # * Stop
                        elif cmd == 0x0204:
                            log = "HOST:%s\tCMD:Stop" % (addr[0])
                            logging.info(log)
                            if options.verbose:
                                print(log)

                            logging.info("Start Speed reduction")
                            while speed > 5:
                                speed -= 5
                                pi.set_PWM_dutycycle(PWM, speed)
                                sleep(1/acc)
                            logging.info("Stop rotator")
                            speed = 0
                            pi.set_PWM_dutycycle(PWM, speed)
                            logging.info("Enable safety break")
                            pi.write(BRAKE, 1)
                        # * Get APOS
                        elif cmd == 0x1020:
                            log = "HOST:%s\tCMD:Get APOS" % (addr[0])
                            logging.info(log)
                            if options.verbose:
                                print(log)
                        else:
                            log = "HOST:%s\tCMD:Unknow" % (addr[0])
                            logging.info(log)
                            if options.verbose:
                                print(log)
                    else:
                        log = "HOST:%s\tError: Checksum failed" % (addr[0])
                        logging.info(log)
                        if options.verbose:
                            print(log)


            except ConnectionResetError:
                logging.error("Connection Reset Error")
                pass
    except KeyboardInterrupt:
        logging.info("Exit APP")
        cmd_sock.close()
        while speed > 5:
            speed -= 5
            pi.set_PWM_dutycycle(PWM, speed)
            sleep(1/acc)
        pi.write(BRAKE, 1)
        pi.stop()
        sys.exit()


if __name__ == '__main__':
    main()
