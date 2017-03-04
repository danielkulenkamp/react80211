#!/usr/bin/python

from helpers.airtime import AirtimeObserver

import optparse
import sys
import time
import numpy

#parser = optparse.OptionParser()
#parser.add_option('-d', '--daemonize',
#                  action='store_true', dest='daemonize', default=False,
#                  help='run as a daemon')
#
#opts, remainder = parser.parse_args()

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

out = open("{}/react.csv".format(sys.argv[1]), 'w')

###
BETA = 0.5
k = 200.0
alloc = 0.20

smooth = None
ct = 0

ao = AirtimeObserver()
while True:
    time.sleep(1.0)
    airtime = ao.airtime()

    ct_ = ct
    smooth = BETA*airtime + (1.0 - BETA)*smooth if smooth else airtime
    ct = int((smooth - alloc)*k) + ct
    ct = 0 if ct < 0 else ct
    ct = 1023 if ct > 1023 else ct
    set_ct(ct)

    out.write('{},{:.5f},{:.5f},{:.5f},{},{}\n'.format(int(time.time()), alloc,
            airtime, smooth, ct_, ct))
    out.flush()

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
