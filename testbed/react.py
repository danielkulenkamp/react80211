
import time
import sys
import signal
from multiprocessing import Process, Queue, Lock
import getopt
import json
import re
from typing import List

import netifaces
from scapy.layers.dot11 import RadioTap
from scapy.layers.dot11 import Dot11
from scapy.sendrecv import sendp, sniff
from helpers.airtime import AirtimeObserver
from helpers.tuning import TunerNew, TunerOld, TunerBase

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
                  my_mac: str, debug: bool, initial_claim: float, sleep_time: float) -> None:
    if debug:
        with console_lock:
            print("react_updater: process started")

    neigh_list = {}

    init_pkt = {
        'claim': 0,
        't': 0,
        'offer': initial_claim,
    }

    neigh_list[my_mac] = init_pkt

    def update_offer() -> None:
        done = False
        a = initial_claim
        d = [key for key, val in neigh_list.items()]
        d_star = []
        while not done:
            d_diff = list(set(d) - set(d_star))
            if set(d) == set(d_star):
                done = True
                neigh_list[my_mac]['offer'] = a + max([val['claim'] for key, val in neigh_list.items()])
            else:
                done = True
                neigh_list[my_mac]['offer'] = a / float(len(d_diff))
                for b in d_diff:
                    if neigh_list[b]['claim'] < neigh_list[my_mac]['offer']:
                        d_star.append(b)
                        a -= neigh_list[b]['claim']
                        done = False

    def update_claim() -> None:
        off_w = [val['offer'] for key, val in neigh_list.items()]
        neigh_list[my_mac]['claim'] = min(off_w)

    # first check sniffer queue
    # then update state
    # then add packet to sender queue
    # then update cw

    while True:
        time.sleep(sleep_time)

        # pull a packet from the sniffer queue
        # save the packet
        if not sniffer_queue.empty():
            pkt = sniffer_queue.get(False)
            neigh_list[pkt[0]] = pkt[1]
        else:
            if debug:
                with console_lock:
                    print(f"react_updater: couldn't pull packet from queue")

        # update_claim, update_offer
        update_offer()
        update_claim()

        # create packet to send to
        neigh_list[my_mac]['t'] = float(time.time())
        pkt_to_send = {
            'claim': neigh_list[my_mac]['claim'],
            't': neigh_list[my_mac]['t'],
            'offer': neigh_list[my_mac]['offer']
        }

        json_data = json.dumps(pkt_to_send)
        sender_queue.put(json_data)

        # check dead nodes
        timeout = 120
        for key, val in neigh_list.items():
            if float(time.time()) - val['t'] > timeout:
                if debug:
                    with console_lock:
                        print(f"Node {key} timeout -- removed")
                neigh_list.pop(key)

        cw_queue.put(neigh_list[my_mac]['claim'])


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
        assert (which_tuner == 'new' or which_tuner == 'old')
        if which_tuner == 'new':
            tuner = TunerNew(interface, log_file, cw_initial, beta, k)
        else:
            tuner = TunerOld(interface, log_file, cw_initial)
    else:
        tuner = TunerBase(interface, log_file)

    ao = AirtimeObserver()
    while True:
        s = sleep_time - ((time.time() - start_time) % sleep_time)
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
    ext_in_opt = ["help", "tdelay=", "iperf_rate=", "enable_react=", "output_path=", "capacity="]
    in_opt = "ht:r:e:o:c:"

    try:
        opts, args = getopt.getopt(sys.argv[1:], in_opt, ext_in_opt)
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err))  # will print something like "option -a not recognized"
        usage(in_opt, ext_in_opt)
        sys.exit(2)

    script_source = '\n \
    #! /bin/bash \n \
    #phy_iface="phy0" \n \
    phy_iface="$1" \n \
    sleeptime="$2" \n \
    labels=$(ls /sys/kernel/debug/ieee80211/${phy_iface}/statistics/) \n \
    arr_label=($labels) \n \
    #sleeptime=2 \n \
    line="" \n \
    stats=$(cat /sys/kernel/debug/ieee80211/${phy_iface}/statistics/*) \n \
    arr_stats_start=($stats); \n \
    #sleep $sleeptime \n \
    #stats=$(cat /sys/kernel/debug/ieee80211/${phy_iface}/statistics/*) \n \
    #arr_stats_stop=($stats); \n \
    printf "{" \n \
    for ((i=0;i<${#arr_label[@]} ;i++)) { \n \
    #diff=$(( ${arr_stats_stop[$i]} - ${arr_stats_start[$i]} )); \n \
    diff=${arr_stats_start[$i]} \n \
    if [ $i -eq $(( ${#arr_label[@]} - 1 )) ]; then \n \
            printf "\'%s\' : %s " "${arr_label[$i]}"  "$diff" \n \
    else \n \
            printf "\'%s\' : %s, " "${arr_label[$i]}" "$diff" \n \
    fi \n \
    } \n \
    printf "}" \n \
    ack_fail=$(( ${arr_stats_stop[0]} - ${arr_stats_start[0]} )) \n \
    tx_completed=$(( ${arr_stats_stop[12]} - ${arr_stats_start[12]} )) \n \
    rts_failed=$(( ${arr_stats_stop[2]} - ${arr_stats_start[2]} )) \n \
    rts_success=$(( ${arr_stats_stop[3]} - ${arr_stats_start[3]} )) \n \
    '

    debug = True

    i_time: float = 0.1
    interface: str = 'wls33'
    mon_interface = 'mon0'
    iperf_rate = 0
    enable_react = False
    tuner = None
    data_path = ""
    start_time = time.time()
    sleep_time = i_time
    claim_capacity = 0.8
    initial_claim: float = 1
    beta = 0.6
    k = 500

    for o, a in opts:
        if o in ("-t", "--tdelay"):
            i_time = float(a)
        if o in ("-r", "--iperf_rate"):
            iperf_rate = float(a)
        if o in ("-e", "--enable_react"):
            enable_react = True
            tuner = a
        if o in ("-o", "--output_path"):
            print("HERE")
            data_path = str(a)
        if o in ("-c", "--capacity"):
            claim_capacity = float(a)
        elif o in ("-h", "--help"):
            usage(in_opt, ext_in_opt)
            sys.exit()

    # INIT REACT INFO
    f_name = '/tmp/ieee_stats.sh'
    ff = open(f_name, 'w')
    ff.write(script_source)
    ff.close()

    global processes
    # we need a queue for each of the three communication paths
    sender_queue = Queue()
    sniffer_queue = Queue()
    cw_queue = Queue()

    # lock for the console
    lock = Lock()

    signal.signal(signal.SIGINT, signal_handler)

    my_mac = str(netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr'])

    print(f"REACT: data path: {data_path}")
    # setup the processes
    sender_process = Process(target=sender, args=(sender_queue, lock, my_mac, i_time, start_time, debug))
    sniffer_process = Process(target=sniffer, args=(sniffer_queue, lock, i_time, my_mac, mon_interface, debug))
    cw_process = Process(target=cw_updater, args=(cw_queue, lock, data_path, enable_react, tuner,
                                                  sleep_time, start_time, claim_capacity, initial_claim, interface,
                                                  beta, k, debug))
    react_updater_process = Process(target=react_updater, args=(sender_queue, sniffer_queue, cw_queue, lock, my_mac,
                                                                debug, initial_claim, sleep_time))

    if enable_react:
        processes = [sender_process, sniffer_process, cw_process, react_updater_process]
    else:
        processes = [cw_process]

    for process in processes:
        process.start()

    while True:
        pass


if __name__ == '__main__':
    main()