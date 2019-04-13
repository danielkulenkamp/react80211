#!/usr/bin/env python

from __future__ import division

import sys
import time

from tuning import TunerBase
from collision_rate import CollisionRateObserver
from airtime import AirtimeObserver

class TunerCollisionRate(TunerBase):

    def __init__(self, iface, log_file, cw_init):
        super(TunerCollisionRate, self).__init__(iface, log_file)

        self.cr_observer = CollisionRateObserver(iface)
        self.ao = AirtimeObserver(iface)

        self.set_cw(cw_init)
        self.cw_prev = cw_init

    def update_cw(self):
        coll_rate = self.cr_observer.collision_rate()
        airtime = self.ao.airtime()

        if coll_rate < .1:
            cw = self.cw_prev / 2
        elif coll_rate > .2:
            cw = self.cw_prev * 2
        else:
            cw = self.cw_prev

        cw = 2 if cw < 2 else cw
        cw = 1023 if cw > 1023 else cw
        cw = int(cw)
        self.set_cw(cw)

        self.log(-1, airtime, self.cw_prev, cw, coll_rate)
        self.cw_prev = cw

if __name__ == '__main__':
    if len(sys.argv) == 2:
        log = open(sys.argv[1], 'w')
    else:
        log = sys.stdout

    tuner = TunerCollisionRate('wlan0', log, 32)
    while True:
        time.sleep(1)
        tuner.update_cw()
