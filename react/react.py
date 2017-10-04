from __future__ import division

import sys
from socket import *
from time import sleep
import struct

from auctioneer import Auctioneer
from bidder import Bidder

#class Trader(object):
#
#    def __init__(self):
#        self.neighbors = set()
#        self.claims = {}

class ReactSocket(object):
    MSG_FMT = '!id'
    MSG_TYPE_CLAIM = 1
    MSG_TYPE_OFFER = 2

    def __init__(self):
        self.s = socket(AF_INET, SOCK_DGRAM)
        self.s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        self.s.bind(('', 5000))

    def offer(self, offer):
        self.broadcast(self.MSG_TYPE_OFFER, offer)

    def bid(self, bid):
        self.broadcast(self.MSG_TYPE_CLAIM, bid)

    def broadcast(self, msg_type, claim):
        msg = struct.pack(self.MSG_FMT, msg_type, claim)
        self.s.sendto(msg, ('10.255.255.255', 5000))

    def recv(self):
        raw_msg, node = self.s.recvfrom(2048)
        msg_type, claim = struct.unpack(self.MSG_FMT, raw_msg)

        offer = bid = None
        if msg_type == self.MSG_TYPE_CLAIM:
            bid = claim
        elif msg_type == self.MSG_TYPE_OFFER:
            offer = claim

        return node, offer, bid

if __name__ == '__main__':
    react = ReactSocket()
    auctioneer = Auctioneer(0.3)
    bidder = Bidder(0.2)

    react.offer(auctioneer.update())
    react.bid(bidder.update())

    old_offer = old_bid = None
    while True:
        node, offer, bid = react.recv()

        if offer:
            new_bid = bidder.store(node, offer)
            if new_bid: react.bid(new_bid)

            if old_bid != new_bid:
                print "Bid: {}".format(new_bid)
                old_bid = new_bid

        if bid:
            new_offer = auctioneer.store(node, bid)
            if new_offer: react.offer(new_offer)

            if old_offer != new_offer:
                print "Offer: {}".format(new_offer)
                old_offer = new_offer

