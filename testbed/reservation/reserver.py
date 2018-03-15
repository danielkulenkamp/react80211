#!/usr/bin/env python2

import sys
import json
import urllib2

def post_json(url, data):
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')

    response = urllib2.urlopen(req, json.dumps(data))
    return json.loads(response.read())

def get_json(url):
    return json.loads(urllib2.urlopen(url).read())

def place_reservation(start, end, amount):
    return post_json('http://{}:5000/reserve'.format(start),
            {'amount': amount, 'destination': end, 'next': True, 'first': True})

def get_status(address):
    return get_json('http://{}:5000/status'.format(address))

if __name__ == '__main__':
    call = sys.argv[1]
    if call == 'place_reservation':
        print json.dumps(place_reservation(sys.argv[2], sys.argv[3], int(sys.argv[4])))
    elif call == 'get_status':
        print json.dumps(get_status(sys.argv[2]))

#    try:
#        print place_reservation('192.168.0.1', '192.168.0.4', 10)
#        print get_status('192.168.0.1')
#        print get_status('192.168.0.2')
#        print get_status('192.168.0.3')
#        print get_status('192.168.0.4')
#
#    except urllib2.HTTPError as e:
#        print e
