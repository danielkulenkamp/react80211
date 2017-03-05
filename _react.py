#!/usr/bin/python

from helpers.airtime import AirtimeObserver

import argparse
import sys
import time
import numpy

p = argparse.ArgumentParser(description='REACT: airtime negotiation/tuning.')
p.add_argument('log_file', action='store', type=argparse.FileType('w'),
        help='file to write REACT log to')
p.add_argument('-b', '--beta', action='store', default=0.5, type=float,
        help='beta value for airtime smoothing')
p.add_argument('-k', action='store', default=200.0, type=float,
        help='k-multiplier for airtime tuning')
p.add_argument('-n', '--no_react', action='store_true',
        help="don't run REACT (but still log airtime)")

args = p.parse_args()

def setCW(iface,qumId,aifs,cwmin,cwmax,burst):
    phy='phy0'
    f_name='/sys/kernel/debug/ieee80211/{}/ath9k/txq_params'.format(phy);
    txq_params_msg='{} {} {} {} {}'.format(qumId,aifs,cwmin,cwmax,burst)
    f_cw = open(f_name, 'w')
    f_cw.write(txq_params_msg)

def set_ct(ct):
    qumId = 1 #BE
    aifs = 2
    cw_min = int(ct)
    cw_max = int(ct)
    burst = 0
    setCW('wlan0', qumId, aifs, cw_min, cw_max, burst)

def set_max(cw):
    qumId = 1 #BE
    aifs = 2
    cw_min = 1
    cw_max = int(cw)
    burst = 0
    setCW('wlan0', qumId, aifs, cw_min, cw_max, burst)

###
alloc = 0.20
smooth = None
ct = 0

ao = AirtimeObserver()
while True:
    time.sleep(1.0)
    airtime = ao.airtime()

    if smooth is None:
        smooth = airtime
    else:
        smooth = args.beta*airtime + (1.0 - args.beta)*smooth

    ct_ = ct
    ct = int((smooth - alloc)*args.k) + ct
    ct = 0 if ct < 0 else ct
    ct = 1023 if ct > 1023 else ct
    if not(args.no_react):
        set_ct(ct)

    args.log_file.write('{:.0f},{:.5f},{:.5f},{:.5f},{},{}\n'.format(
            time.time(), alloc, airtime, smooth, ct_, ct))
    args.log_file.flush()

###
#n = 1.0
#avg = 0.0
#ao = AirtimeObserver()
#while True:
#    time.sleep(1.0)
#    airtime = ao.airtime()
#
#    avg += (airtime - avg) / n
#    n += 1
#
#    out.write('{},{:.5f},{:.5f}\n'.format(int(time.time()), airtime, avg))
#    out.flush()
###
