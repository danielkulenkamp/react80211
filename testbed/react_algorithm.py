
import time
import math

DEBUG = False


class REACT:
    def __init__(self, name: str, capacity: float = 1, be_magnitude: float = 1, qos_magnitude: float = 0) -> None:
        assert (math.isclose(be_magnitude, 0, rel_tol=1e-5) ^ (math.isclose(qos_magnitude, 0, rel_tol=1e-5))), \
            "Either be_magnitude or qos_magnitude must be 0!"

        # name of node in REACT auctions -- usually will be the
        # MAC address of the STA running REACT
        self.name: str = name

        # Total capacity of the STA's medium to be offered up
        self._capacity: float = capacity                  # c

        # the amount of BE airtime this STA wants
        self._be_magnitude: float = be_magnitude                 # w

        # the amount of QOS airtime this STA wants
        # mutually exclusive with _be_magnitude
        self._qos_magnitude: float = qos_magnitude

        # set of adjacent bidders that are requesting airtime
        # from the current STA's auction
        self._bidders: set[str] = set()               # D

        # set of adjacent auctions that the current STA is
        # requesting airtime at
        self._auctions: set[str] = set()              # R

        # dict of offers from adjacent auctions -- the current
        # STA will update its claim based on these offers
        # the dict contains keys (names of adjacent nodes) with
        # values which are the claim dicts (timestamp, claim)
        self._be_offers = {}

        # dict of claims from adjacent bidders -- the current STA
        # will update its offer based on these claims.
        # this dict is similar to _offers, in that it is a dict of
        # dicts that store the claim info
        self._be_claims = {}

        # this dict contains qos offers from adjacent auctions. If
        # at least one of these is 0, that means that our request was
        # rejected and we must use the BE offer from _offers instead
        self._qos_offers = {}

        # this dict contains qos claims from adjacent bidders that we
        # will try to satisfy. If we can't satisfy any of them, then
        # we send them a response with an airtime of 0
        self._qos_claims = {}

        # this is where all timestamps are stored for the adjacent auctions
        self._timestamps = {}

        # TODO: Check if be_magnitude is 0? If there is a qos_magnitude
        #       it should be 0.
        if qos_magnitude > be_magnitude:
            self.new_qos_claim(self.name, self._qos_magnitude)
            self.new_be_claim(self.name, self._be_magnitude)
        else:
            self.new_be_claim(self.name, self._be_magnitude)

        self.print_all_offers()

        self.update_claim()
        self.update_offer()

    # private func for adding a be claim to the be claim dict.
    def _add_be_claim(self, name, be_claim, timestamp=time.time()):
        self._timestamps[name] = float(timestamp)

        self._be_claims[name] = be_claim

    # private func for adding a qos claim to the qos offer dict
    def _add_qos_claim(self, name, qos_claim, timestamp=time.time()):
        self._timestamps[name] = float(timestamp)

        self._qos_claims[name] = qos_claim

    # private func for adding an offer to the be offer dict.
    # if its a qos offer, it will be placed in the _qos_offer dict
    def _add_be_offer(self, name, be_offer, timestamp=time.time()):
        self._timestamps[name] = float(timestamp)

        self._be_offers[name] = be_offer

    # private func for adding a qos offer to the qos offer dict
    def _add_qos_offer(self, name, qos_offer, timestamp=time.time()):
        self._timestamps[name] = float(timestamp)

        self._qos_offers[name] = qos_offer

    def qos_items(self):
        to_return = []
        for bidder, offer in self._qos_offers.items():
            to_return.append([bidder, offer])

        return to_return

    # NOTE: - Can't use this anymore, because we need to update the
    #       claims separately due to having qos and be claims
    # # public convenience function for adding a claim and offer
    # # at the same time. This is used in the manager class, because
    # # this way both claim and offer get the same timestamp
    # def new_offer_claim(self, name, offer, claim, qos=False):
    #     timestamp = time.time()

    #     if name not in self._auctions:
    #         self._join_auction(name)
    #     if name not in self._bidders:
    #         self._new_bidder(name)

    #     self._add_claim(name, claim, qos=qos, timestamp=timestamp)
    #     self._add_offer(name, offer, qos=qos, timestamp=timestamp)

    # public function for getting the most recent timestamp of the
    # STA's current offer and claim
    def get_timestamp(self, name=None):
        if name:
            return self._timestamps[name]
        else:
            return self._timestamps[self.name]

    # public function for updating the timestamp of the current STA's
    # offer and claim. This is used if the claim/offer haven't changed
    def update_timestamp(self, name=None):
        if name:
            self._timestamps[name] = float(time.time())
        else:
            self._timestamps[self.name] = float(time.time())

    # checks if any of the timeouts have timed out. This is used
    # to detect stations that have left the auction
    def check_timeouts(self, timeout):

        for name, timestamp in self._timestamps.items():
            if time.time() - timestamp > timeout:
                self.leave_auction(name)
                self.remove_bidder(name)

    # Bidder Functions

    # updates the magnitude of the medium being requested by this
    # station. The new claim is then calculated based on this claim
    # and the offers of the adjacent auctions.
    def update_magnitude(self, new_magnitude, qos=False):
        if qos:
            self._be_magnitude = 0
            self._qos_magnitude = new_magnitude
        else:
            self._be_magnitude = new_magnitude
            self._qos_magnitude = 0

        self.update_claim()

    # when a new qos offer from an adjacent auction is received, this
    # function saves the offer and calculates the new claim
    def new_qos_offer(self, auction, offer):
        if auction not in self._auctions:
            self._join_auction(auction)
        self._add_qos_offer(auction, offer)
        self.update_claim()

    def new_be_offer(self, auction, offer):
        if auction not in self._auctions:
            self._join_auction(auction)
        self._add_be_offer(auction, offer)
        self.update_claim()

    # private function used to add adjacent auctions to the auction set
    def _join_auction(self, auction):
        self._auctions.add(auction)

    # used to leave an auction
    def leave_auction(self, auction):
        self._auctions.remove(auction)
        if auction in self._qos_offers:
            del self._qos_offers[auction]
        elif auction in self._be_offers:
            del self._be_offers[auction]
        self.update_claim()

    # this function updates the STA's claim based on offers from adjacent
    # auctions and the STA's current magnitude
    def update_claim(self):
        if self._qos_magnitude > 0:
            # we check all of the received qos offers.
            # there won't be entries until we've received one
            # from an adjacent station, so this only gets executed
            # if we have already received an offer. and if that
            # offer is less than what we requested, it is 0, and
            # we must switch to be then.
            # TODO: There might be an error here
            can_claim_qos = True
            for _, qos_offer in self._qos_offers.items():
                if qos_offer < self._qos_magnitude:
                    # the offer is 0, so we switch to BE
                    # self._qos_magnitude = False
                    self._be_magnitude = self._qos_magnitude
                    self._qos_magnitude = 0  # new change to try and fix error
                    can_claim_qos = False
                    break

            if can_claim_qos:
                self._add_qos_claim(self.name, self._qos_magnitude)
        # else:
        # TODO: Need to be able to remove QoS claims if the node decides to
        # switch from BE back to QoS. Somehow that needs to happen
        # remove the qos claim from the dictionary

        # This used to be in an else block with the above if, but I don't think that
        # was right. This should happen regardless so that the BE offer is adjusted
        # when the magnitudes are changed.
        be_offers = [be_offer for auction, be_offer in self._be_offers.items()]
        be_offers.append(self._be_magnitude)
        self._add_be_claim(self.name, min(be_offers))

        if DEBUG:
            print(f'BE Claims: {self._be_claims}')
            print(f'QOS Claims: {self._qos_claims}')

    # returns the current claim of the current STA
    def get_be_claim(self, name=None):
        if not name:
            name = self.name
        if name not in self._be_claims:
            return None
        if name:
            return self._be_claims[name]
        else:
            return self._be_claims[self.name]

    def get_qos_claim(self, name=None):
        if not name:
            name = self.name
        if name not in self._qos_claims:
            return None
        if name:
            return self._qos_claims[name]
        else:
            return self._qos_claims[self.name]

    def get_claim(self, name=None):
        if name:
            pass
        else:
            if self._qos_magnitude > self._be_magnitude:
                return self.get_qos_claim()
            else:
                return self.get_be_claim()

    # Auctioneer Functions

    # updates the total capacity that this STA has available
    # to offer to adjacent bidders
    def update_capacity(self, new_capacity):
        self._capacity = new_capacity
        self.update_offer()

    # saves new claims as they arrive, and updates the current
    # STA's offer based on these claims from adjacent auctions
    def new_be_claim(self, bidder, claim):
        if bidder not in self._bidders:
            self._new_bidder(bidder)
        self._add_be_claim(bidder, claim)
        self.update_offer()

    def new_qos_claim(self, bidder, claim):
        if bidder not in self._bidders:
            self._new_bidder(bidder)
        self._add_qos_claim(bidder, claim)
        self.update_offer()

    # private func for adding new bidders to the bidders set
    def _new_bidder(self, bidder):
        self._bidders.add(bidder)

    # removes bidder from the current auction
    def remove_bidder(self, bidder):
        self._bidders.remove(bidder)
        if bidder in self._qos_claims:
            del self._qos_claims[bidder]
        elif bidder in self._be_claims:
            del self._be_claims[bidder]
        self.update_offer()

    # updates the current offer based on the claims from adjacent
    # bidders and the total capacity available.
    def update_offer(self):
        be_star = set()
        qos_star = set()
        available = self._capacity
        done = False

        while not done:
            # if all bidders are in qos_star + be_star, then this auction
            # doesn't constrain any of them
            if be_star.union(qos_star) == self._bidders:
                done = True
                claims = [be_claim for bidder, be_claim in self._be_claims.items()]
                if not claims:
                    claims.append(0)
                self._add_be_offer(self.name, available + max(claims))
            # else this auction constrains at least one bidder
            else:
                done = True

                # we start by trying to service QOS airtime
                qos_offer = available
                qos_set = set([bidder for bidder in self._bidders if bidder in self._qos_claims])

                for qos_bidder in qos_set.difference(qos_star):
                    if self._qos_claims[qos_bidder] <= qos_offer:
                        # we can satisfy this bidder
                        print(f'{self.name} here')
                        self._add_qos_offer(qos_bidder, self._qos_claims[qos_bidder])

                        qos_star.add(qos_bidder)
                        available = available - self._qos_claims[qos_bidder]
                        qos_offer = qos_offer - self._qos_claims[qos_bidder]
                        done = False
                    else:
                        # we can't satisfy the bidder, so we must downgrade it to a BE request
                        # we will have to notify the bidder somehow too I guess, that's for the manager to do
                        qos_claim = self._qos_claims[qos_bidder]
                        self.new_be_claim(qos_bidder, qos_claim)
                        self._qos_claims.pop(qos_bidder, None)
                        done = False

                be_set = set([bidder for bidder in self._bidders if bidder in self._be_claims])
                # we offer remaining airtime in equal portions to
                # the constrained bidders
                offer = available / len(be_set.difference(be_star)) if len(be_set.difference(be_star)) > 0 else available
                self._add_be_offer(self.name, offer)  # TODO: - why is this here??? I'm not sure.
                # construct Dstar and compute available for new offer
                for bidder in (be_set.difference(be_star)):
                    if self._be_claims[bidder] < offer:
                        be_star.add(bidder)
                        available = available - self._be_claims[bidder]
                        done = False

        if DEBUG:
            print(f'BE Offers: {self._be_offers}')
            print(f'QOS Offers: {self._qos_offers}')

    def get_be_offer(self, name=None):
        if name:
            return self._be_offers[name]
        else:
            return self._be_offers[self.name]

    def get_qos_offer(self, name=None):
        if name:
            return self._qos_offers[name]
        else:
            return self._qos_offers[self.name]

    def print_all_offers(self):
        self.qos_items()
        print(self.name)
        print("QOS (offers/claims)")
        print(self._qos_offers)
        print('-')
        print(self._qos_claims)
        print("BE (offers/claims)")
        print(self._be_offers)
        print('-')
        print(self._be_claims)
