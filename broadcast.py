#!/usr/bin/python

import argparse
import sys
from socket import *

SO_PRIORITY = 12
SO_MARK = 36

p = argparse.ArgumentParser()
p.add_argument('-t', '--transmit', action='store_true',
        help='Broadcast packets instead of listening')
args = p.parse_args()

s = socket(AF_INET, SOCK_DGRAM)
if args.transmit:
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    s.setsockopt(SOL_SOCKET, SO_MARK, 1)
    s.connect(('192.168.0.255', 9999))
else:
    s.bind(('192.168.0.255', 9999))

i = 0
while 1:
    if args.transmit:
        s.send(str(i))
        i += 1
    else:
        print s.recv(1024)
