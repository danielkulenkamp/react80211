import sys
from flask import Flask, jsonify, request
import threading
import struct
import socket
import urllib2

from reserver import post_json

if len(sys.argv) < 3:
    print 'Usage: reservation_server.py MY_IP N1_IP [N2_IP N3_IP ...]'
    exit(1)

def dot2long(ip):
    return struct.unpack("!L", socket.inet_aton(ip))[0]

my_ip = sys.argv[1]
neighbors = sys.argv[2:]

next_ip = None
for n in neighbors:
    raw_my_ip = dot2long(my_ip)
    raw_ip = dot2long(n)

    if raw_my_ip < raw_ip and (next_ip is None or raw_ip < dot2long(next_ip)):
        next_ip = n

print "MY_IP:{} NEXT_IP:{} NEIGH:{}".format(my_ip, next_ip, neighbors)

capacity_lock = threading.Lock()
capacity = 80
allocation = 0

def unreserve(amount, deallocate=False):
    global capacity
    global allocation
    with capacity_lock:
        capacity += amount
        if deallocate:
            allocation -= amount

def reserve(amount, allocate=False):
    global capacity
    global allocation
    with capacity_lock:
        if amount <= capacity:
            capacity -= amount
            if allocate:
                allocation += amount
            return True
        else:
            return False

class ReservationException(Exception):
    pass

def forward_reservation(ip, reservation):
    resp = post_json('http://{}:5000/reserve'.format(ip), reservation)
    if not(resp['placed']):
        raise ReservationException(resp['reason'])

app = Flask(__name__)

@app.route('/status')
def status():
    return jsonify({'capacity': capacity, 'allocation': allocation})

@app.route('/cancel', methods=['POST'])
def cancel_reservation():
    amount = request.json['amount']
    unreserve(amount)
    return jsonify({'success': True})

@app.route('/reserve', methods=['POST'])
def make_reservation():
    def fail(reason):
        return jsonify({'placed': False, 'reason': reason})

    # KeyError exception results in HTTP error, which is good and fine
    reservation = request.json
    amount = reservation['amount']
    destination = reservation['destination']
    _next = reservation['next']
    first = reservation['first']

    # If first we don't need to reserve for API caller
    if not(first):
        if not(reserve(amount)):
            return fail('Not enough capacity at {}'.format(my_ip))

    if _next and dot2long(destination) != dot2long(my_ip):
        #  Reserve capacity for forwarding traffic and forward reservation

        # TODO: compute next_ip based on destination
        assert next_ip is not None, \
                'Being next and not the destination implies next_ip is not none'

        # Reserve and allocate for self, we need allocation since we're on path
        if not(reserve(amount, allocate=True)):
            unreserve(amount)
            return fail('Not enough capacity at {}'.format(my_ip))
        else:
            reservation['first'] = False

        try:
            # Tell neighbors (other than next) that you will be forwarding
            reservation['next'] = False
            for i in range(len(neighbors)):
                neighbor = neighbors[i]
                if dot2long(neighbor) != dot2long(next_ip):
                    forward_reservation(neighbor, reservation)

            reservation['next'] = True
            forward_reservation(next_ip, reservation)

        except (ReservationException, urllib2.HTTPError, urllib2.URLError) as e:
            if not(first):
                unreserve(amount)
            unreserve(amount, deallocate=True)

            # Cancel reservation at nodes already reached
            for j in range(i):
                neighbor = neighbors[j]
                # Next node already unreserved for itself if it failed
                if dot2long(neighbor) != dot2long(next_ip):
                    # No try/except, give up if error with previously OK node
                    post_json('http://{}:5000/cancel'.format(neighbor),
                            reservation)

            return fail(str(e))

    return jsonify({'placed': True})

app.run(debug=True, threaded=True, host='0.0.0.0')
