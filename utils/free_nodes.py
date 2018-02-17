#!/usr/bin/env python

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

import sys

d = webdriver.Chrome()
d.get('http://boss.wilab2.ilabt.iminds.be/reservation/index.php/reserve/new')

raw_input('Hit Enter after you have logged in...')

while True:
    print d.find_element_by_name('startdate').get_attribute('value')

    for hour in xrange(24):
        time_fmt = Keys.BACKSPACE*5 + '{:02}:{:02}'

        # update free nodes
        d.find_element_by_name('starthour').send_keys(time_fmt.format(hour, 1))
        d.find_element_by_name('endhour').send_keys(time_fmt.format(hour, 59))
        d.find_element_by_name('refresh').click()
        d.execute_script('showhide("free_ZOTAC")')

        # print free nodes
        sys.stdout.write('{:02}:'.format(hour))
        nodes = []
        for node in d.find_elements_by_partial_link_text('zotac'):
            nodes.append(node.text)
        nodes.sort()
        sys.stdout.write(' ' + ' '.join(nodes))
        sys.stdout.write('\n')

    raw_input('Hit Enter to re-run...')
    sys.stdout.write('\n')
