from __future__ import division

class Bidder(object):

    def __init__(self, demand):
        self.resources = set()
        self.demand = float(demand)
        self.offers = {}

    def store(self, node, offer):
        if node not in self.offers.keys():
            old = None
            print "New auction: {}".format(node)
        else:
            old = self.offers[node]
        self.offers[node] = float(offer)

        if old != self.offers[node]:
            return self.update()
        else:
            return None

    def update(self):
        return min(self.offers.values() + [self.demand])

