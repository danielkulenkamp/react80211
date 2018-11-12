#!/usr/bin/env python

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import pendulum

import sys

d = webdriver.Chrome()
d.get('http://boss.wilab2.ilabt.iminds.be/reservation/index.php/reserve/new')

raw_input('Hit Enter after you have logged in...')

while True:
    today = d.find_element_by_name('startdate').get_attribute('value')
    print today
    year, month, day = map(int, today.split('-'))

    for hour in xrange(24):
        time_fmt = Keys.BACKSPACE*5 + '{:02}:{:02}'

        # update free nodes
        d.find_element_by_name('starthour').send_keys(time_fmt.format(hour, 1))
        d.find_element_by_name('endhour').send_keys(time_fmt.format(hour, 59))
        d.find_element_by_name('refresh').click()
        d.execute_script('showhide("free_ZOTAC")')

        # print free nodes
        time = pendulum.datetime(year, month, day, hour, tz='Europe/Brussels')
        time_phx = time.in_timezone('America/Phoenix')
        nodes = d.find_elements_by_partial_link_text('zotac')

        sys.stdout.write("[{:02}] {}: {}\n".format(hour,
                time_phx.format('dddd Do [of] MMMM YYYY HH:mm A') , len(nodes)))

    raw_input('Hit Enter to re-run...')
    sys.stdout.write('\n')
