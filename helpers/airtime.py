#!/usr/bin/python

from __future__ import division

import subprocess
import sys
import time

class AirtimeObserver(object):

    def __init__(self, dev='wlan0'):
        self.cmd = ['iw', dev, 'survey', 'dump']
        self.iw_survey_dump()

    def skip(self, i, to):
        while i < len(self.output):
            if self.output[i] == to:
                break
            else:
                i += 1

        return i

    def iw_survey_dump(self):
        self.output = subprocess.check_output(self.cmd).split()

        i = 0
        i = self.skip(i, '[in')
        i = self.skip(i, 'active')

        self.active = float(self.output[i + 2])

        i = self.skip(i, 'transmit')

        self.transmit = float(self.output[i + 2])

    def airtime(self):
        old_active = self.active
        old_transmit = self.transmit

        self.iw_survey_dump()

        if old_active != self.active:
            return (self.transmit - old_transmit) / (self.active - old_active)
        else:
            return 0.0

if __name__ == '__main__':
    if len(sys.argv) == 2:
        sleep_time = int(sys.argv[1])
    else:
        sleep_time = 1

    ao = AirtimeObserver()
    while True:
        time.sleep(sleep_time)
        print ao.airtime()

