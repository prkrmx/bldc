#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Rotator v2 control"""

import sys
import logging
import subprocess
import pigpio

from socket import *
from time import sleep
from optparse import OptionParser
from multiprocessing import Process, Value, Queue
from read_RPM import reader

BUF_SIZE = 1

def chks(buf):
    chks = 0
    for index in range(1, len(buf) - 1):
        chks += buf[index]
    return chks % 256

def parity(num):
    result = 0
    while num:
        result ^= num & 1
        num >>= 1
    return result

def log_msg(msg, verbose, error = False):
    if error:
        logging.error(msg)
    else:
        logging.info(msg)
    if verbose:
        print(msg)

def argument_parser():
    parser = OptionParser(usage="\nsudo ./rttr_v2.py -l 50007 -p 50008 -v\n"
                          "sudo ./rttr_v2.py -k\n"
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
    # sudo kill -9 $(ps ax | grep rttr_v2.py | grep -v "grep" | awk '{print $1}')
    log_msg("Kill all rttr processes!", False)
    subprocess.Popen(
        'sudo kill -9 $(ps ax | grep rttr_v2.py | grep -v "grep" | awk \'{print $1}\')',
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log_msg("Exit", False)
    sys.exit(0)


def sensors(options, position, speed):
    log_msg("Set Broadcast socket %s@%d" % (options.addr, options.port), options.verbose)
    bcast_sock = socket(AF_INET, SOCK_DGRAM)
    bcast_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    bcast_sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    log_msg("Connect sensors GPIO", options.verbose)
    pi_enc = pigpio.pi()

    log_msg("Open encoder SPI", options.verbose)
    encoder = pi_enc.spi_open(0, 1000000, 3)

    RPM_GPIO = 6
    log_msg("Set up RPM reader: GPIO %d" % (RPM_GPIO), options.verbose)
    tach = reader(pi_enc, RPM_GPIO, 2125, 0.5, 0.5)

    prev_pos = -1
    try:
        while True:
            # Read RPM
            rpm_f = tach.RPM()

            # Read position
            c, d = pi_enc.spi_read(encoder, 3)
            if c == 3:
                word = ((d[0] << 16) | (d[1] << 8) | d[2]) >> 7
                pos_f = (word >> 6)*360/1024
                bit_parity = parity(word >> 1)
                if ((word & 0x38) == 0x20) and ((word & 0x01) == bit_parity):
                    pos_i = round(pos_f)
                    rpm_i = round(rpm_f)
                    if prev_pos != pos_i:
                    # if pos_i > prev_pos:
                        if pos_i == 360:
                            pos_i = 0
                        prev_pos = pos_i
                        buffer = bytes([0xFF]) + rpm_i.to_bytes(1, 'big') + pos_i.to_bytes(2, 'big')
                        buffer += chks(buffer + bytes([0x00])).to_bytes(1, 'big')
                        bcast_sock.sendto(buffer, (options.addr, options.port))
                        if options.verbose:
                            print("RPM {:d}\t POS:{:d}\t{:b}".format(rpm_i, pos_i, word))
                    position.value = pos_i
                    speed.value = rpm_i
            sleep(.001)
    except:
        bcast_sock.close()
        tach.cancel()
        pi_enc.spi_close(encoder)
        pi_enc.stop()
        log_msg("Oops! %s occurred." % (sys.exc_info()[0]), options.verbose, True)
        

# Main worker
def do_work(options, pi, position, speed, queue):
    log_msg("Init main worker", options.verbose)
    
    spd = 0   # Rotator current speed in samples
    rpm = 0   # Rotator current speed in rpm
    acc = 0   # Rotator acceleration
    spin = 0  # Rotator direction

    PWM = 13
    DIR = 19
    BRAKE = 26
    log_msg("Set PMW frequency & dutycycle", options.verbose)
    pi.set_PWM_frequency(PWM, 100000)
    pi.set_PWM_dutycycle(PWM, 0)

    log_msg("Set GPIO mode", options.verbose)
    pi.set_mode(DIR, pigpio.OUTPUT)
    pi.set_mode(BRAKE, pigpio.OUTPUT)

    log_msg("Set direction & brake", options.verbose)
    pi.write(DIR, 1)    # 1-CW 0-CCW
    pi.write(BRAKE, 1)  # 0-run 1-stop

    while True:
        if not queue.empty():
            data = queue.get(True)
            cmd = (data[1] << 8) | data[2]
            
            if cmd == 0x0102:   #* Start
                rpm = data[3]
                acc = data[4]
                spin = data[5]

                log_msg("CMD:Start\tRPM:%d\tACC:%d\tDIR:%s" % (rpm, acc, "CW" if spin else "CCW"), options.verbose)

                if pi.read(BRAKE):
                    log_msg("Disable safety break", options.verbose)
                    pi.write(BRAKE, 0)

                log_msg("Setting direction", options.verbose)
                pi.write(DIR, spin)

                max_spd = int(rpm*23.18)
                if max_spd > 255:
                     max_spd = 255

                log_msg("Setting speed to %d. Start rotator" % (max_spd), options.verbose)
                while spd < max_spd:
                    pi.set_PWM_dutycycle(PWM, spd)
                    spd += 5
                    sleep(1/acc)
            elif cmd == 0x0408: #* GoTo
                rpm = data[3]
                acc = data[4]
                pos = (data[5] << 8) | data[6]
                log_msg("CMD:GoTo\tRPM:%d\tACC:%d\tPOS:%d" % (rpm, acc, pos), options.verbose)

                if pi.read(BRAKE):
                    log_msg("Disable safety break", options.verbose)
                    pi.write(BRAKE, 0)

                log_msg("Setting speed to 2.5 RPM. Start rotator", options.verbose)
                while True:
                    if (spd > 70):
                        spd -= 5
                    elif (spd < 65):
                        spd += 5
                    else:
                        break
                    pi.set_PWM_dutycycle(PWM, spd)
                    sleep(.1)

                log_msg("Waiting for the required position", options.verbose)
                while (pos-options.shift) % 360 != position.value:
                    if not queue.empty():
                        break
                    else:
                        sleep(.001)

                log_msg("Stop rotator", options.verbose)
                while spd > 0:
                    spd -= 5
                    pi.set_PWM_dutycycle(PWM, spd)
                    sleep(.1)
                log_msg("Enable safety break", options.verbose)
                pi.write(BRAKE, 1)
            elif cmd == 0x0810: #* Update
                rpm = data[3]
                acc = data[4]
                log_msg("CMD:Update\tRPM:%d, ACC:%d" % (rpm, acc), options.verbose)

                if pi.read(BRAKE):
                    log_msg("The rotator does not move! Nothing to do!", options.verbose)
                else:
                    max_spd = int(rpm*23.18)
                    if max_spd > 255:
                        max_spd = 255

                    if max_spd > spd:
                        log_msg("Increase speed to %d." % (max_spd), options.verbose)
                        while spd < max_spd:
                            spd += 5
                            pi.set_PWM_dutycycle(PWM, spd)
                            sleep(1/acc)
                    else:
                        log_msg("Reducing speed to %d." % (max_spd), options.verbose)
                        while spd > max_spd:
                            spd -= 5
                            pi.set_PWM_dutycycle(PWM, spd)
                            sleep(1/acc)
            elif cmd == 0x0204: #* Stop
                log_msg("CMD:Stop", options.verbose)
                log_msg("Start Speed reduction", options.verbose)
                while spd > 5:
                    spd -= 5
                    pi.set_PWM_dutycycle(PWM, spd)
                    sleep(1/acc)
                log_msg("Stop rotator", options.verbose)
                spd = 0
                pi.set_PWM_dutycycle(PWM, spd)
                log_msg("Enable safety break", options.verbose)
                pi.write(BRAKE, 1)
            elif cmd == 0x1020: #* Get APOS
                log_msg("CMD:Get APOS", options.verbose)
            else:
                log_msg("CMD:Unknow", options.verbose, True)
        sleep(.001)

def main(options=None):
    if options is None:
        (options, args) = argument_parser().parse_args()
    logging.basicConfig(filename='/var/log/rttr.log', format='%(asctime)s\t%(process)d\t%(levelname)s\t%(message)s', level=logging.INFO)

    if options.kill:
        kill_exit()

    log_msg("Starting GPIO daemonn", options.verbose)
    subprocess.Popen(['sudo pigpiod'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sleep(.2)

    log_msg("Connected GPIO", options.verbose)
    pi = pigpio.pi()
    if not pi.connected:
        log_msg("GPIO not connected! Exit!", options.verbose, True)
        exit(0)

    cmd_queue = Queue(BUF_SIZE)
    abs_poss = Value('i', 0)
    abs_speed = Value('i', 0)
    log_msg("Start sensors background worker", options.verbose)
    sp = Process(target=sensors, args=(options, abs_poss, abs_speed))
    sp.start()

    log_msg("Start main background worker", options.verbose)
    mp = Process(target=do_work, args=(options, pi, abs_poss, abs_speed, cmd_queue))
    mp.start()

    log_msg("Open Commands listener port: %d" % (options.lstr), options.verbose) 
    cmd_sock = socket(AF_INET, SOCK_STREAM)
    cmd_sock.bind(('', options.lstr))
    cmd_sock.listen(1)
    conn, addr = cmd_sock.accept()

    while True:
        try:
            data_rx = conn.recv(16)
            if not data_rx:
                conn, addr = cmd_sock.accept()

            if len(data_rx) > 7:

                apos = abs_poss.value.to_bytes(2, 'big')
                abs_spd = abs_speed.value.to_bytes(2, 'big')

                fbk = bytearray(8)
                fbk[0] = 0xFF
                fbk[1] = data_rx[1]
                fbk[2] = data_rx[2]
                fbk[3] = apos[0]
                fbk[4] = apos[1]
                fbk[5] = abs_spd[1]
                fbk[7] = chks(fbk)
                conn.send(fbk)
                
                if chks(data_rx) == data_rx[7]:
                    log_msg("HOST:%s\tGot new command" % (addr[0]), options.verbose)
                    if not cmd_queue.full():
                        cmd_queue.put(data_rx)
                    else:
                        log_msg("HOST:%s\tError: Queue full" % (addr[0]), options.verbose, True)
                else:
                    log_msg("HOST:%s\tError: Checksum failed" % (addr[0]), options.verbose, True)
        except ConnectionResetError:
            log_msg("Connection Reset Error", options.verbose, True)
            pass

if __name__ == '__main__':
    main()
