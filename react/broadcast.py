#!/usr/bin/python

from __future__ import division

import json
#import argparse
import time
from collections import namedtuple
from socket import *

class React(object):

    def __init__(self, capacity=0.8, demand=0.2):
        self.capacity = capacity
        self.demand = demand

        self.ReactState = namedtuple('ReactState', 'offer claim')
        self.neighbors = {}

    def offer(self):
        if len(self.neighbors) > 0:
            return self.capacity / len(self.neighbors)
        else:
            return self.capacity

    def claim(self):
        offers = [n.offer for n in self.neighbors.values()]
        return min(offers + [self.demand])

class ReactSocket(React):

    def __init__(self, capacity=0.8, demand=1.0,
            broadcast_address=('192.168.0.255', 9999)):
        super(ReactSocket, self).__init__(capacity=capacity, demand=demand)

        #SO_PRIORITY = 12
        SO_MARK = 36

        self.sendr = socket(AF_INET, SOCK_DGRAM)
        self.sendr.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        self.sendr.setsockopt(SOL_SOCKET, SO_MARK, 1)
        self.sendr.connect(broadcast_address)

        self.recvr = socket(AF_INET, SOCK_DGRAM)
        self.recvr.bind(('192.168.0.255', 9999))

    def run(self):
        state = self.ReactState(self.offer(), self.claim())
        self.sendr.send(json.dumps(state))
        print state

        data = self.recvr.recvfrom(1024)
        state = self.ReactState(*json.loads(data[0]))
        self.neighbors[data[1]] = state

#p = argparse.ArgumentParser()
#p.add_argument('-t', '--transmit', action='store_true',
#        help='Broadcast packets instead of listening')
#args = p.parse_args()

r = ReactSocket()
while True:
    r.run()
    time.sleep(0.5)
