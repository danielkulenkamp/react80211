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

#cw = 1330
#ao = AirtimeObserver()
#while cw >= 0:
#    set_cw(cw)
#
#    airtimes = []
#    ao.airtime()
#    for i in xrange(10):
#        time.sleep(1)
#        airtimes.append(ao.airtime())
#
#    out.write('{},{},{}\n'.format(cw, numpy.average(airtimes),
#        numpy.std(airtimes)))
#    out.flush()
#
#    cw -= 10

smooth = None
BETA = 0.3

alloc = 0.20

MAX_CT = 1024
MIN_CT = 1
ct = 512

ao = AirtimeObserver()
while True:
    time.sleep(1.0)
    airtime = ao.airtime()

    ###
    if smooth is None:
        smooth = airtime
    else:
        smooth = BETA*airtime + (1.0 - BETA)*smooth

    ct_ = int((smooth - alloc) * 100.0) + ct

    if ct_ > MAX_CT:
        ct_ = MAX_CT
    elif ct_ < MIN_CT:
        ct_ = MIN_CT

    ct_ = int(ct_)
    ###
    #ct_ = ct
    ###

    out.write('{},{:.5f},{:.5f},{:.5f},{}\n'.format(int(time.time()), alloc, airtime, smooth, ct_))
    out.flush()

    set_ct(ct_)
    ct = ct_
