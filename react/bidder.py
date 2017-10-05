from __future__ import division

class Bidder(object):

    def __init__(self, demand):
        self.resources = set()
        self.demand = float(demand)
        self.offers = {}

    def store(self, node, offer):
        self.offers[node] = float(offer)

    def update(self):
        claim = min(self.offers.values() + [self.demand])
        return claim
