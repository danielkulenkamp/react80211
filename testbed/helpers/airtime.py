#!/usr/bin/python

from __future__ import division

import subprocess
import time
import argparse

from observer import Observer

def iw_survey_dump(dev):
    cmd = ['iw', dev, 'survey', 'dump']
    output = subprocess.check_output(cmd).split()
    survey = {}

    def skip(output, i, to):
        while i < len(output):
            if output[i] == to:
                break
            else:
                i += 1
        return i

    i = 0
    i = skip(output, i, '[in')

    i = skip(output, i, 'active')
    survey['active'] = float(output[i + 2])

    i = skip(output, i, 'busy')
    survey['busy'] = float(output[i + 2])

    i = skip(output, i, 'receive')
    survey['receive'] = float(output[i + 2])

    i = skip(output, i, 'transmit')
    survey['transmit'] = float(output[i + 2])

    return survey

class ChannelObserver(Observer):

    def __init__(self, dev='wlan0'):
        super(ChannelObserver, self).__init__(iw_survey_dump, dev)

class AirtimeObserver(Observer):

    def __init__(self, dev='wlan0'):
        super(AirtimeObserver, self).__init__(iw_survey_dump, dev)

    def airtime(self):
        self.update()

        active = self.surveysays('active')
        transmit = self.surveysays('transmit')

        if active != 0:
            return transmit/active
        else:
            return 0.0

if __name__ == '__main__':
    p = argparse.ArgumentParser(
            description="Measure airtime using 'iw DEV survey dump'.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('-d', '--dev', action='store', default='wlan0',
            help='wireless interface')
    p.add_argument('-t', '--sleep_time', action='store', default=1.0, type=float,
            help='time (in seconds) to pause between airtime measurements')
    p.add_argument('-o', '--once', action='store_true',
            help="measure airtime once and exit")

    args = p.parse_args()

    ao = AirtimeObserver(args.dev)
    while True:
        time.sleep(args.sleep_time)
        print ao.airtime()

        if args.once:
            break
