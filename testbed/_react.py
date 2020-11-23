#! /usr/bin/python

import getopt
import json
import re
import sys
import time
from typing import List
import threading

import netifaces
# from scapy.all import *
from scapy.layers.dot11 import RadioTap
from scapy.layers.dot11 import Dot11
from scapy.sendrecv import sendp, sniff
from helpers.airtime import AirtimeObserver
from helpers.tuning import TunerNew, TunerOld, TunerBase

neigh_list = {}
C = 1
CLAIM_CAPACITY = 0.8
mon_interface = "mon0"
debug = False
start_time = time.time()

MAX_THR = 5140  # kbps

my_mac: str = ''


def init(interface: str) -> None:
    """Initializes some REACT information"""
    global my_mac
    my_mac = str(netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr'])
    init_pkt = {
        'claim': 0,
        't': 0,
        'offer': C,
    }

    neigh_list[my_mac] = init_pkt


def update_cw(interface: str, enable_react: bool, sleep_time: int, data_path: str,
              which_tuner: str, beta: float, k: int, prealloc: float) -> None:
    """Update contention window"""
    global my_mac
    log_file = open(data_path, 'w')
    cw_initial = 0

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
        time.sleep(sleep_time - ((time.time() - start_time) % sleep_time))
        airtime = ao.airtime()

        alloc = float(CLAIM_CAPACITY) * float(neigh_list[my_mac]['claim'])
        tuner.update_cw(alloc + prealloc, airtime)


def update_offer() -> None:
    done = False
    a: int = C
    global my_mac
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
    off_w.append(neigh_list[my_mac]['w'])
    neigh_list[my_mac]['claim'] = min(off_w)


# def sniffer_REACT(iface: str, i_time: float) -> None:
def sniffer_react(i_time: float) -> None:
    call_timeout = i_time*5
    call_count = 10
    while True:
        packet_list = sniff(iface=mon_interface,
                            count=call_count,
                            timeout=call_timeout,
                            store=1,
                            filter="ether dst ff:ff:ff:ff:ff:ff")

        print(len(packet_list))
        for packet in packet_list:
            try:
                rx_mac = str(packet.addr2)
                if rx_mac == my_mac:
                    pass
                else:
                    payload = bytes(packet[3])
                    if 'claim' in str(payload):
                        print('claim in packet')
                        # TODO: Make sure that removing the \{ and \} don't mess up the correctness
                        payload = '{' + re.search(r'{(.*)}', str(payload)).group(1) + '}'
                        curr_pkt = json.loads(payload)
                        neigh_list[str(rx_mac)] = curr_pkt
                        curr_pkt['t'] = float(time.time())
                        update_offer()
                        update_claim()
            except Exception as err:
                if debug:
                    print("exception", err)
                pass


# def send_ctrl_msg(iface: str, json_data: str) -> None:
def send_ctrl_msg(json_data: str) -> None:
    a = RadioTap() / Dot11(addr1="ff:ff:ff:ff:ff:ff", addr2=my_mac, addr3="ff:ff:ff:ff:ff:ff") / json_data
    sendp(a, iface=mon_interface, verbose=0)


# def send_react_msg(interface: str, i_time: float, iperf_rate: float, enable_react: bool) -> None:
def send_react_msg(i_time: float, iperf_rate: float) -> None:
    global my_mac
    while True:
        w_rate = min(
            int(C),
            int((iperf_rate * C) / float(MAX_THR))
        )

        neigh_list[my_mac]['w'] = w_rate

        try:
            neigh_list[my_mac]['t'] = float(time.time())
            pkt_to_send = {
                'claim': neigh_list[my_mac]['claim'],
                't': neigh_list[my_mac]['t'],
                'offer': neigh_list[my_mac]['offer'],
                # 'w': neigh_list[my_mac]['w'],
            }

            json_data = json.dumps(pkt_to_send)

            # check dead nodes
            timeout = 120

            for key, val in neigh_list.items():
                if float(time.time()) - val['t'] > timeout:
                    print(f'Node {key} timeout -- removed')
                    neigh_list.pop(key)
            update_offer()
            update_claim()
            # REACT variables updated, transmit!
            send_ctrl_msg(json_data)

        except Exception as err:
            if debug:
                print("Exception: {}".format(err))
            pass

        time.sleep(i_time / 10 - ((time.time() - start_time) % (i_time / 10)))


def usage(in_opt: str, ext_in_opt: List[str]) -> None:
    print("input error: here optionlist: \n{0} --> {1}\n".format(in_opt, str(ext_in_opt)))


def main():
    ext_in_opt = ["help", "iface=", "tdelay=", "iperf_rate=", "enable_react=", "output_path=", "beta=", "kay=",
                  "capacity=", "prealloc="]
    in_opt = "hi:t:r:e:o:b:k:c:p:"

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

    i_time: float = 0
    interface: str = 'wls33'
    iperf_rate = 0
    enable_react = False
    which_tuner = None
    data_path = ""
    beta = 0.6
    k = 500
    pre_allocation: float = 0

    global CLAIM_CAPACITY
    for o, a in opts:
        if o in ("-i", "--iface"):
            interface = a
        if o in ("-t", "--tdelay"):
            i_time = float(a)
        if o in ("-r", "--iperf_rate"):
            iperf_rate = float(a)
        if o in ("-e", "--enable_react"):
            enable_react = True
            which_tuner = a
        if o in ("-o", "--output_path"):
            data_path = str(a)
        if o in ("-b", "--beta"):
            beta = float(a)
        if o in ("-k", "--kay"):
            k = float(a)
        if o in ("-c", "--capacity"):
            CLAIM_CAPACITY = float(a)
        if o in ("-p", "--prealloc"):
            pre_allocation = float(a)
        elif o in ("-h", "--help"):
            usage(in_opt, ext_in_opt)
            sys.exit()
    # INIT REACT INFO
    f_name = '/tmp/ieee_stats.sh'
    ff = open(f_name, 'w')
    ff.write(script_source)
    ff.close()

    init(interface)
    try:
        # Thread transmitter
        threading.Thread(
            target=send_react_msg,
            args=(i_time, iperf_rate)
        ).start()

        # thread receiver
        threading.Thread(
            target=sniffer_react,
            args=(i_time,)
        ).start()

        # update cw
        threading.Thread(
            target=update_cw,
            args=(interface, enable_react, 1, data_path, which_tuner, beta, k, pre_allocation)
        ).start()

    except Exception as err:
        print("Error: unable to start thread -- {}".format(err))

    while 1:
        pass


if __name__ == "__main__":
    main()
