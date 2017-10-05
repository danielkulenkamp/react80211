from __future__ import division

class Auctioneer(object):

    def __init__(self, capacity):
        self.demands = set()
        self.capacity = float(capacity)
        self.claims = {}

    def store(self, node, claim):
        self.claims[node] = float(claim)

    def update(self):
        demands = set(self.claims)
        satisfied = set()
        airtime = self.capacity
        done = False
        while not(done):
            if satisfied == demands:
                done = True
                offer = airtime
                if len(self.claims.values()):
                    offer += max(self.claims.values())
            else:
                done = True
                difference = demands.difference(satisfied)
                offer = airtime / len(difference)
                for b in difference:
                    if self.claims[b] < offer:
                        satisfied.add(b)
                        airtime -= self.claims[b]
                        done = False
        return offer
