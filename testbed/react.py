
import time
import sys
import signal
from multiprocessing import Process, Queue, Lock
import getopt
import json
import re
import math
from typing import List

import netifaces
from scapy.layers.dot11 import RadioTap
from scapy.layers.dot11 import Dot11
from scapy.sendrecv import sendp, sniff
from helpers.airtime import AirtimeObserver
from helpers.tuning import TunerSALT, TunerRENEW, TunerBase
from react_algorithm import REACT

processes = []


def signal_handler(sig, frame):
    global processes
    print("you pressed ctrl c")
    for p in processes:
        p.terminate()
        p.join()

    for p in processes:
        print(p.exitcode)
    sys.exit()


def react_updater(sender_queue: Queue, sniffer_queue: Queue, cw_queue: Queue, console_lock: Lock,
                  my_mac: str, debug: bool, qos: bool, maximum_capacity: float, initial_claim: float,
                  sleep_time: float) -> None:
    if debug:
        with console_lock:
            print("react_updater: process started")

    if qos:
        react = REACT(my_mac, capacity=maximum_capacity, be_magnitude=0, qos_magnitude=initial_claim)
    else:
        react = REACT(my_mac, capacity=maximum_capacity, be_magnitude=initial_claim, qos_magnitude=0)

    if debug:
        with console_lock:
            react.print_all_offers()

    # first check sniffer queue
    # then update state
    # then add packet to sender queue
    # then update cw

    while True:
        time.sleep(sleep_time)

        # pull a packet from the sniffer queue
        # save the packet
        if not sniffer_queue.empty():
            neigh_name, packet = sniffer_queue.get(False)
            react.new_be_offer(neigh_name, packet['be_offer'])

            if math.isclose(0, packet['be_claim']):
                # we have a qos claim
                react.new_qos_claim(neigh_name, packet['qos_claim'])
            else:
                # we have a be claim
                react.new_be_claim(neigh_name, packet['be_claim'])

            for dictionary in packet['qos']:
                if dictionary['sta_name'] == react.name:
                    react.new_qos_offer(neigh_name, dictionary['qos_offer'])

        else:
            if debug:
                with console_lock:
                    print(f"react_updater: couldn't pull packet from queue")

        # update_claim, update_offer
        react.update_offer()
        react.update_claim()

        # create packet to send to
        pkt_to_send = {}
        react.update_timestamp()
        pkt_to_send['t'] = react.get_timestamp()
        pkt_to_send['be_offer'] = react.get_be_offer()
        pkt_to_send['be_claim'] = react.get_be_claim()
        pkt_to_send['qos_claim'] = react.get_qos_claim()

        items = react.qos_items()

        qos_offers = []
        for offer in items:
            sta = {
                'sta_name': offer[0],
                'qos_offer': offer[1],
            }
            qos_offers.append(sta)

        pkt_to_send['qos'] = qos_offers

        json_data = json.dumps(pkt_to_send)
        sender_queue.put(json_data)

        # check dead nodes
        timeout = 120
        react.check_timeouts(timeout)

        cw_queue.put(react.get_claim())


def sender(queue: Queue, console_lock: Lock, my_mac: str, i_time: float,
           start_time: float, debug: bool) -> None:
    if debug:
        with console_lock:
            print("sender: process started")

    def send_ctrl_msg(json_data: str, mon_interface: str = 'mon0') -> None:
        a = RadioTap() / Dot11(addr1="ff:ff:ff:ff:ff:ff", addr2=my_mac, addr3="ff:ff:ff:ff:ff:ff") / json_data
        sendp(a, iface=mon_interface, verbose=0)

    # first we have to get the initial packet. So we need to wait until the react updater gives us one
    packet_to_send = queue.get()

    while True:
        if not queue.empty():
            packet_to_send = queue.get(False)
        else:
            if debug:
                with console_lock:
                    print('SENDER PROCESS: Queue was empty, so we should use the same packet')

        # send the packet
        try:
            send_ctrl_msg(packet_to_send)
        except Exception as err:
            if debug:
                with console_lock:
                    print(f'sender exception: {err}')
            pass

        time.sleep(i_time / 10 - ((time.time() - start_time) % (i_time / 10)))


def sniffer(queue: Queue, console_lock: Lock, i_time: float, my_mac: str, mon_interface: str, debug: bool) -> None:
    if debug:
        with console_lock:
            print("sniffer: process started")

    call_timeout = i_time
    call_count = 10
    packet_filter = 'ether dst ff:ff:ff:ff:ff:ff'

    while True:
        packet_list = sniff(iface=mon_interface, count=call_count, timeout=call_timeout, store=1, filter=packet_filter)

        for packet in packet_list:
            try:
                rx_mac = str(packet.addr2)
                if rx_mac != my_mac:
                    payload = bytes(packet[3])
                    if 'claim' in str(payload):
                        if debug:
                            with console_lock:
                                print('claim in packet')
                        # TODO: Make sure that removing the \{ and \} don't mess up the correctness
                        payload = '{' + re.search(r'{(.*)}', str(payload)).group(1) + '}'

                        if debug:
                            with console_lock:
                                print(f'sniffer: payload -> {payload}')
                        curr_pkt = json.loads(payload)

                        # pass the packet to the react updater process
                        queue.put((rx_mac, curr_pkt))
            except Exception as err:
                if debug:
                    with console_lock:
                        print("sniffer exception: ", err)
                pass


def cw_updater(queue: Queue, console_lock: Lock, data_path: str, enable_react: bool,
               which_tuner: str, sleep_time: int, start_time: float, claim_capacity: float,
               initial_claim: float, interface: str, beta: float, k: int, debug: bool) -> None:
    if debug:
        with console_lock:
            print("cw_updater: process started")
            print(f"cw_updater: data path is {data_path}")

    log_file = open(data_path, 'w')
    cw_initial = 0

    current_claim = initial_claim

    if enable_react:
        assert (which_tuner == 'salt' or which_tuner == 'renew')
        if which_tuner == 'salt':
            tuner = TunerSALT(interface, log_file, cw_initial, beta, k)
        elif which_tuner == 'renew':
            tuner = TunerRENEW(interface, log_file, cw_initial)
        else:
            raise Exception("Unknown tuner type!")
    else:
        tuner = TunerBase(interface, log_file)

    ao = AirtimeObserver()
    while True:
        s = sleep_time - ((time.time() - start_time) % sleep_time)
        s = 1

        with console_lock:
            print(f"s time: {s}")
        time.sleep(s)

        # we check if the queue has a new claim for us
        if not queue.empty():
            current_claim = float(queue.get(False))
        else:
            if debug:
                with console_lock:
                    print("Queue was empty, it should just use the old value")

        # get the airtime, calculate the allocation
        airtime = ao.airtime()
        alloc = float(claim_capacity) * current_claim
        tuner.update_cw(alloc, airtime)


def usage(in_opt: str, ext_in_opt: List[str]) -> None:
    print("input error: here optionlist: \n{0} --> {1}\n".format(in_opt, str(ext_in_opt)))


def main() -> None:
    ext_in_opt = ["help", "tdelay=", "iperf_rate=", "enable_react=", "output_path=", "claim=", "qos="]
    in_opt = "ht:r:e:o:c:q:"

    try:
        opts, args = getopt.getopt(sys.argv[1:], in_opt, ext_in_opt)
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err))  # will print something like "option -a not recognized"
        usage(in_opt, ext_in_opt)
        sys.exit(2)

    debug = True

    i_time: float = 0.1
    interface: str = 'wls33'
    mon_interface = 'mon0'
    enable_react = False
    tuner = None
    data_path = ""
    start_time = time.time()
    sleep_time = i_time
    maximum_capacity = 1
    offered_capacity = 0.8
    initial_claim: float = maximum_capacity
    beta = 0.6
    k = 500
    qos = False

    for o, a in opts:
        if o in ("-t", "--tdelay"):
            i_time = float(a)
        if o in ("-e", "--enable_react"):
            enable_react = True
            tuner = a
        if o in ("-o", "--output_path"):
            print("HERE")
            data_path = str(a)
        if o in ("-c", "--claim"):
            initial_claim = float(a)
        if o in ("-q", "--qos"):
            qos = bool(a)
        elif o in ("-h", "--help"):
            usage(in_opt, ext_in_opt)
            sys.exit()

    global processes
    # we need a queue for each of the three communication paths
    sender_queue = Queue()
    sniffer_queue = Queue()
    cw_queue = Queue()

    # lock for the console
    lock = Lock()

    signal.signal(signal.SIGINT, signal_handler)

    my_mac = str(netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr'])

    # setup the processes
    sender_process = Process(
        target=sender,
        args=(sender_queue, lock, my_mac, i_time, start_time, debug)
    )

    sniffer_process = Process(
        target=sniffer,
        args=(sniffer_queue, lock, i_time, my_mac, mon_interface, debug)
    )

    cw_process = Process(
        target=cw_updater,
        args=(cw_queue, lock, data_path, enable_react, tuner, sleep_time, start_time,
              offered_capacity, initial_claim, interface, beta, k, debug)
    )

    react_updater_process = Process(
        target=react_updater,
        args=(sender_queue, sniffer_queue, cw_queue, lock, my_mac, debug, qos, maximum_capacity,
              initial_claim, sleep_time)
    )

    if enable_react:
        processes = [sender_process, sniffer_process, cw_process, react_updater_process]
    else:
        processes = [cw_process]

    print(f'Num threads: {len(processes)}')
    for process in processes:
        process.start()

    while True:
        pass


if __name__ == '__main__':
    main()
