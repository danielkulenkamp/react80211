#!/usr/bin/python

from helpers.airtime import AirtimeObserver

import argparse
import time

class TunerBase(object):

    def __init__(self, iface, log_file):
        # TODO: implement iface --> phy translation
        assert(iface == 'wlan0')
        phy = 'phy0'

        self.txq_params_fname = '/sys/kernel/debug/ieee80211/'
        self.txq_params_fname += phy
        self.txq_params_fname += '/ath9k/txq_params'

        self.log_file = log_file

    def set_cw(self, cw):
        qumId = 1 #BE
        aifs = 2
        cwmin = int(cw)
        cwmax = int(cw)
        burst = 0

        txq_params_msg = '{} {} {} {} {}'.format(qumId, aifs, cwmin, cwmax,
                burst)
        f_cw = open(self.txq_params_fname, 'w')
        f_cw.write(txq_params_msg)
        f_cw.close()

    def log(self, alloc, airtime, cw_prev, cw):
        self.log_file.write('{:.0f},{:.5f},{:.5f},{},{}\n'.format(
                time.time(), alloc, airtime, cw_prev, cw))
        self.log_file.flush()

    def update_cw(self, alloc, airtime, cw_prev):
        self.log(alloc, airtime, cw_prev, -1)
        return -1

class TunerNew(TunerBase):

    def __init__(self, iface, log_file, cw_init, k):
        super(TunerNew, self).__init__(iface, log_file)

        self.k = k
        self.cw_prev = cw_init
        self.smooth = None

        self.set_cw(cw_init)

    def update_cw(self, alloc, airtime):
        beta = 0.5
        if self.smooth is None:
            self.smooth = airtime
        else:
            self.smooth = beta*airtime + (1.0 - beta)*self.smooth

        cw = int((self.smooth - alloc)*self.k) + self.cw_prev
        cw = 0 if cw < 0 else cw
        cw = 1023 if cw > 1023 else cw
        self.set_cw(cw)

        self.log(alloc, airtime, self.cw_prev, cw)
        self.cw_prev = cw

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='New CW tuning implementation.',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('log_file', action='store', type=argparse.FileType('w'),
            help='file to write REACT log to')
    p.add_argument('-k', action='store', default=200.0, type=float,
            help='k-multiplier for airtime tuning')
    p.add_argument('-n', '--no_tuning', action='store_true',
            help="don't actually do any tuning (but still log airtime)")
    p.add_argument('-c', '--cw_initial', action='store', default=0, type=int,
            help='initial CW value')
    p.add_argument('-t', '--sleep_time', action='store', default=1.0,
            type=float, help='length (in seconds) of observation interval')
    p.add_argument('-a', '--airtime_alloc', action='store', default=0.20,
            type=float, help='airtime allocated to this node via REACT')
    args = p.parse_args()

    if args.no_tuning:
        tuner = TunerBase('wlan0', args.log_file)
    else:
        tuner = TunerNew('wlan0', args.log_file, args.cw_initial, args.k)

    ao = AirtimeObserver()
    while True:
        time.sleep(args.sleep_time)
        airtime = ao.airtime()

        tuner.update_cw(args.airtime_alloc, airtime)
