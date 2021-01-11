#!/usr/bin/python

import sys
import argparse
import time
import subprocess
import statistics

from helpers.airtime import AirtimeObserver, ChannelObserver
from helpers.collision_rate import CollisionRateObserver


class TunerBase(object):

    def __init__(self, iface, log_file):
        # TODO: implement iface --> phy translation
        assert(iface == 'wls33')
        phy = 'phy0'

        self.cr_observer = CollisionRateObserver(iface)

        self.txq_params_fname = '/sys/kernel/debug/ieee80211/'
        self.txq_params_fname += phy
        self.txq_params_fname += '/ath9k/txq_params'

        self.log_file = log_file

    def set_cw(self, cw):
        qumId = 1  # BE
        aifs = 2
        cwmin = int(cw)
        cwmax = int(cw)
        burst = 0

        txq_params_msg = '{} {} {} {} {}'.format(qumId, aifs, cwmin, cwmax, burst)
        f_cw = open(self.txq_params_fname, 'w')
        f_cw.write(txq_params_msg)
        f_cw.close()

    def log(self, alloc, airtime, cw_prev, cw, cr):
        self.log_file.write('{:.5f},{:.5f},{:.5f},{},{},{:.5f}\n'.format(
                time.time(), alloc, airtime, cw_prev, cw, cr))
        self.log_file.flush()

    def update_cw(self, alloc, airtime):
        self.log(alloc, airtime, -1, -1, self.cr_observer.collision_rate())


class TunerSALTNew(TunerBase):

    def __init__(self, iface, log_file, cw_init, beta1, beta2, k1, k2, drastic=False, num_vals=50, threshold=None):
        super(TunerSALTNew, self).__init__(iface, log_file)
        print('New SALT Tuner')

        self.cr_observer = CollisionRateObserver(iface)

        self.k1 = k1
        self.k2 = k2
        self.beta1 = beta1
        self.beta2 = beta2
        self.cw_prev = cw_init
        self.smooth = None
        self.drastic = drastic
        self.use_variance = False if threshold else True
        self.threshold = threshold
        self.num_vals = num_vals

        self.last_values = []

        self.set_cw(cw_init)

    def update_cw(self, alloc, airtime):
        if len(self.last_values) == 0:
            self.last_values.append(airtime)
        self.last_values.append(airtime)

        if len(self.last_values) > self.num_vals:
            self.last_values.pop(0)

        if self.use_variance:
            self.threshold = statistics.variance(self.last_values)

        print(self.threshold)

        if airtime > (alloc + self.threshold):# or airtime < (alloc - self.threshold):
            beta = self.beta2
            k = self.k2
        else:
            beta = self.beta1
            k = self.k1

        if self.smooth is None:
            self.smooth = airtime
        else:
            self.smooth = beta * airtime + (1.0 - beta) * self.smooth

        max_cw = 1023*4

        cw = int((self.smooth - alloc) * k) + self.cw_prev
        cw = 0 if cw < 0 else cw
        cw = max_cw if cw > max_cw else cw
        if self.drastic and airtime > (alloc + self.threshold):
            cw = max_cw

        self.set_cw(cw)

        self.log(alloc, airtime, self.cw_prev, cw, self.cr_observer.collision_rate())
        self.cw_prev = cw


class TunerSALT(TunerBase):

    def __init__(self, iface, log_file, cw_init, beta, k):
        super(TunerSALT, self).__init__(iface, log_file)

        self.cr_observer = CollisionRateObserver(iface)

        self.k = k
        self.beta = beta
        self.cw_prev = cw_init
        self.smooth = None

        self.set_cw(cw_init)

    def update_cw(self, alloc, airtime):
        if self.smooth is None:
            self.smooth = airtime
        else:
            self.smooth = self.beta*airtime + (1.0 - self.beta)*self.smooth

        cw = int((self.smooth - alloc)*self.k) + self.cw_prev
        cw = 0 if cw < 0 else cw
        cw = 1023 if cw > 1023 else cw
        self.set_cw(cw)

        self.log(alloc, airtime, self.cw_prev, cw, self.cr_observer.collision_rate())
        self.cw_prev = cw


class TunerRENEW(TunerBase):

    def __init__(self, iface, log_file, cw_init):
        super(TunerRENEW, self).__init__(iface, log_file)

        self.cmd = ['cat', '/sys/kernel/debug/ieee80211/phy0/statistics/dot11RTSSuccessCount']

        self.cr_observer = CollisionRateObserver(iface)

        self.observer = ChannelObserver()
        self.n = int(subprocess.check_output(self.cmd))
        self.n_old = None
        self.cw_prev = cw_init

    def update_cw(self, alloc, airtime):
        self.observer.update()
        busy = self.observer.surveysays('busy')

        self.n_old = self.n
        self.n = int(subprocess.check_output(self.cmd))
        n = self.n - self.n_old

        n_alloc = n*alloc if n*alloc != 0 else 1
        cw = int((2/9e-3)*(airtime*((1 - alloc)/(n_alloc))*busy))
        cw = 0 if cw < 0 else cw
        cw = 1023 if cw > 1023 else cw
        self.set_cw(cw)

        self.log(alloc, airtime, self.cw_prev, cw,
                 self.cr_observer.collision_rate())
        self.cw_prev = cw


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='New CW tuning implementation.',
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('-k', action='store', default=200.0, type=float,
                   help='k-multiplier for airtime tuning')
    p.add_argument('-b', action='store', default=0.6, type=float, help='beta value')
    p.add_argument('-n', '--no_tuning', action='store_true',
                   help="don't actually do any tuning (but still log airtime)")
    p.add_argument('-z', '--new_version', action='store_true')
    p.add_argument('-c', '--cw_initial', action='store', default=0, type=int,
                   help='initial CW value')
    p.add_argument('-t', '--sleep_time', action='store', default=1.0,
                   type=float, help='length (in seconds) of observation interval')
    p.add_argument('-a', '--airtime_alloc', action='store', default=0.20,
                   type=float, help='airtime allocated to this node via REACT')
    p.add_argument('-y', '--renew', action='store_true')
    args = p.parse_args()

    if args.new_version:
        tuner = TunerSALTNew('wls33', sys.stdout, args.cw_initial, 0.6, 0.6, 500, 500, drastic=True, threshold=0.05)
    elif args.no_tuning:
        # TODO: change this back to TunerBase??
        tuner = TunerBase('wls33', sys.stdout)
    elif args.renew:
        print('Tuner Renew')
        tuner = TunerRENEW('wls33', sys.stdout, args.cw_initial)
    else:
        tuner = TunerSALT('wls33', sys.stdout, args.cw_initial, args.b, args.k)

    ao = AirtimeObserver()
    while True:
        time.sleep(args.sleep_time)
        airtime = ao.airtime()

        tuner.update_cw(args.airtime_alloc, airtime)
