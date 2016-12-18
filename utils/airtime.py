#!/usr/bin/python

from __future__ import division

import subprocess
import re
import sys
import time

def parse_survey_time(line):
    return float(re.findall(r'\d+ ms', line)[0].split()[0]) / 1000

def iw_survey_dump(dev='wlan0'):
    cmd = ['iw', dev, 'survey', 'dump']
    output = subprocess.check_output(cmd).split('\n')

    for i in xrange(len(output)):
        line = output[i]
        if re.search(r'frequency:.*\[in use\]$', line):
            active = parse_survey_time(output[i + 1])
            busy = parse_survey_time(output[i + 2])
            recv = parse_survey_time(output[i + 3])
            xmit = parse_survey_time(output[i + 4])

            return active, busy, recv, xmit

if __name__ == '__main__':
    if len(sys.argv) == 2:
        sleep_time = int(sys.argv[1])
    else:
        sleep_time = 10

    while True:
        active_start, _, _, xmit_start = iw_survey_dump()
        time.sleep(sleep_time)
        active_end, _, _, xmit_end = iw_survey_dump()

        print (xmit_end - xmit_start) / (active_end - active_start)

