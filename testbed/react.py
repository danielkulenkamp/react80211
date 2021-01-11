
import time
import sys
import signal
from multiprocessing import Process, Queue, Lock
import subprocess
import json
import re
import os
import math
from typing import List
import argparse

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
        # p.join()

    for p in processes:
        print(p.exitcode)
    sys.exit()


def usage(in_opt: str, ext_in_opt: List[str]) -> None:
    print("input error: here optionlist: \n{0} --> {1}\n".format(in_opt, str(ext_in_opt)))


class React(Process):

    def __init__(self, algorithm: str = 'dot', output_path: str = None,
                 claim: float = 1.0, qos: bool = False, debug: bool = False):
        Process.__init__(self)

        # Inter process cooperation vars
        self._processes = []
        self._sender_queue = Queue()
        self._sniffer_queue = Queue()
        self._cw_queue = Queue(maxsize=1)
        self._new_claims_queue = Queue()
        self._console_lock = Lock()

        # React vars
        self._i_time: float = 0.1
        self._interface: str = 'wls33'
        self._mon_interface: str = 'mon0'
        self._enable_react = False

        assert(algorithm == 'salt' or algorithm == 'dot' or algorithm == 'renew')

        if algorithm == 'salt':
            self._enable_react = True
        elif algorithm == 'renew':
            self._enable_react = True

        self._algorithm: str = algorithm
        self._data_path: str = output_path
        self._start_time: float = time.time()
        self._sleep_time: float = self._i_time
        self._maximum_capacity: float = 1
        self._offered_capacity = 0.8
        self._initial_claim: float = claim
        self._beta = 0.6
        self._k = 500
        self._qos = qos

        # shaping vars
        self._max_bandwith = 6
        # self._shaper_value = f'{round(self._initial_claim * self._max_bandwith, 1)}mbit'
        self._shaper_value = None
        self._debug = debug

        self._counter = 0

        self.my_mac = str(netifaces.ifaddresses(self._interface)[netifaces.AF_LINK][0]['addr'])

    def _update_shaper(self, current_claim):
        new_shaper_value = f'{round(self._offered_capacity * current_claim * self._max_bandwith, 1)}mbit'

        if self._debug:
            with self._console_lock:
                print(f'old shaper value: {self._shaper_value}')
                print(f'new shaper value: {new_shaper_value}')

        if self._shaper_value != new_shaper_value:
            self._shaper_value = new_shaper_value
            command = f'sudo tc class change dev {self._interface} parent 1:0 classid 1:1 htb rate {self._shaper_value}'

            if self._debug:
                with self._console_lock:
                    print(f'running command: {command}')

            subprocess.run([command], shell=True)

    def _react_updater(self) -> None:
        if self._debug:
            with self._console_lock:
                print("react_updater: process started")

        if self._qos:
            react = REACT(self.my_mac, capacity=self._maximum_capacity, be_magnitude=0, qos_magnitude=self._initial_claim)
        else:
            react = REACT(self.my_mac, capacity=self._maximum_capacity, be_magnitude=self._initial_claim, qos_magnitude=0)

        if self._debug:
            with self._console_lock:
                react.print_all_offers()

        # first check for updated claims
        # then check sniffer queue
        # then update state
        # then add packet to sender queue
        # then update cw

        while True:
            time.sleep(self._sleep_time)

            # check for updated claims
            if not self._new_claims_queue.empty():
                qos, demand = self._new_claims_queue.get(False)
                react.update_magnitude(demand, qos=qos)

            # pull a packet from the sniffer queue
            # save the packet
            if not self._sniffer_queue.empty():
                if self._debug:
                    with self._console_lock:
                        print(f'Got new packet from sniffer queue')
                new_packets = {}
                while not self._sniffer_queue.empty():
                    neigh_name, packet = self._sniffer_queue.get(False)
                    new_packets[neigh_name] = packet

                for neigh_name, packet in new_packets.items():
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
                if self._debug:
                    with self._console_lock:
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
            self._sender_queue.put(json_data)

            # check dead nodes
            timeout = 120
            # react.check_timeouts(timeout)

            current_claim = react.get_claim()
            if self._debug:
                with self._console_lock:
                    print(f'get_claim: {current_claim}')

            self._update_shaper(current_claim)

            if self._cw_queue.empty():
                self._cw_queue.put(current_claim)

            if self._counter % 20 == 0:
                with self._console_lock:
                    react.print_all_offers()

            self._counter = (self._counter % 20) + 1

    def _cw_updater(self) -> None:
        if self._debug:
            with self._console_lock:
                print("cw_updater: process started")
                print(f"cw_updater: data path is {self._data_path}")

        log_file = open(self._data_path, 'w')
        cw_initial = 0

        if self._enable_react:
            assert (self._algorithm == 'salt' or self._algorithm == 'renew')
            if self._algorithm == 'salt':
                tuner = TunerSALT(self._interface, log_file, cw_initial, self._beta, self._k)
            elif self._algorithm == 'renew':
                tuner = TunerRENEW(self._interface, log_file, cw_initial)
            else:
                raise Exception("Unknown tuner type!")
        else:
            tuner = TunerBase(self._interface, log_file)

        current_claim = self._initial_claim
        ao = AirtimeObserver()
        while True:
            s = self._sleep_time - ((time.time() - self._start_time) % self._sleep_time)
            s = 1

            time.sleep(s)

            if self._enable_react:
                # we check if the queue has a new claim for us
                if not self._cw_queue.empty():
                    current_claim = float(self._cw_queue.get(False))
                    if self._debug:
                        with self._console_lock:
                            print(f"Queue had current claim of {current_claim}")
                # else:
                #     if self._debug:
                #         with self._console_lock:
                #             print("Queue was empty, it should just use the old value")

            # get the airtime, calculate the allocation
            airtime = ao.airtime()
            alloc = float(self._offered_capacity) * current_claim
            tuner.update_cw(alloc, airtime)

    def _sender(self) -> None:

        def send_ctrl_msg(json_data: str, my_mac: str, mon_interface: str = 'mon0') -> None:
            a = RadioTap() / Dot11(addr1="ff:ff:ff:ff:ff:ff", addr2=my_mac, addr3="ff:ff:ff:ff:ff:ff") / json_data
            sendp(a, iface=mon_interface, verbose=0)

        if self._debug:
            with self._console_lock:
                print("sender: process started")

        # first we have to get the initial packet. So we need to wait until the react updater gives us one
        packet_to_send = self._sender_queue.get()

        while True:
            if not self._sender_queue.empty():
                packet_to_send = self._sender_queue.get(False)
            # else:
                # if self._debug:
                #     with self._console_lock:
                #         print('SENDER PROCESS: Queue was empty, so we should use the same packet')

            # send the packet
            try:
                send_ctrl_msg(packet_to_send, self.my_mac)
            except Exception as err:
                if self._debug:
                    with self._console_lock:
                        print(f'sender exception: {err}')
                pass

            time.sleep(self._i_time / 10 - ((time.time() - self._start_time) % (self._i_time / 10)))

    def _sniffer(self):
        if self._debug:
            with self._console_lock:
                print("sniffer: process started")

        call_timeout = self._i_time
        call_count = 10
        packet_filter = 'ether dst ff:ff:ff:ff:ff:ff'

        while True:
            packet_list = sniff(iface=self._mon_interface, count=call_count, timeout=call_timeout, store=1,
                                filter=packet_filter)

            for packet in packet_list:
                try:
                    rx_mac = str(packet.addr2)
                    if rx_mac != self.my_mac:
                        payload = bytes(packet[3])
                        if 'claim' in str(payload):
                            # if self._debug:
                            #     with self._console_lock:
                            #         print('claim in packet')
                            # TODO: Make sure that removing the \{ and \} don't mess up the correctness
                            payload = '{' + re.search(r'{(.*)}', str(payload)).group(1) + '}'

                            if self._debug:
                                with self._console_lock:
                                    print(f'sniffer: payload -> {payload}')
                            curr_pkt = json.loads(payload)

                            # pass the packet to the react updater process
                            self._sniffer_queue.put((rx_mac, curr_pkt))
                except Exception as err:
                    if self._debug:
                        with self._console_lock:
                            print("sniffer exception: ", err)
                    pass

    def terminate(self):
        for process in self._processes:
            with self._console_lock:
                print("Terminating REACT")

            process.terminate()
            process.join()

        for process in self._processes:
            print(process.exitcode)

    def new_demand(self, qos, demand) -> None:
        self._new_claims_queue.put((qos, demand))

    def run(self) -> None:
        sender_process = Process(
            target=self._sender,
            args=()
        )

        sniffer_process = Process(
            target=self._sniffer,
            args=()
        )

        cw_process = Process(
            target=self._cw_updater,
            args=()
        )

        react_updater_process = Process(
            target=self._react_updater,
            args=()
        )

        if self._enable_react:
            if self._debug:
                with self._console_lock:
                    print('Starting all processes')
            self._processes = [sender_process, sniffer_process, cw_process, react_updater_process]
        else:
            if self._debug:
                with self._console_lock:
                    print('Starting just cw process')
            self._processes = [cw_process]

        if self._debug:
            with self._console_lock:
                print(f'Num threads: {len(self._processes)}')

        try:
            for process in self._processes:
                process.start()
        except Exception as err:
            print(err)
            print('Error: unable to start threads')
            self.terminate()

        while True:
            pass


def restricted_float(x):
    try:
        x = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{x} not a floating-point literal')

    if not (0.0 <= x <= 1.0):
        raise argparse.ArgumentTypeError(f'{x} not in range [0.0, 1.0]')
    return x


def path_exists(filepath):
    parts = os.path.split(filepath)
    if not os.path.exists(parts[0]):
        raise argparse.ArgumentTypeError(f'{parts[0]} is not a valid directory')
    return filepath


def file_exists(file):
    if not os.path.isfile(file):
        raise argparse.ArgumentTypeError(f'{file} does not exist')
    return file


def main() -> None:
    global processes

    parser = argparse.ArgumentParser()
    parser.add_argument('tuner_algorithm', choices=['salt', 'renew', 'dot'], type=str,
                        help='algorithm used to perform tuning of contention window')
    parser.add_argument('output_file', type=path_exists, help='file used for logging REACT info')
    parser.add_argument('initial_claim', type=restricted_float,
                        help='initial claim for react algorithm, between 0 and 1 (0% and 100%)')
    parser.add_argument('-e', '--experiment_file', type=file_exists,
                        help='runs react in dynamic mode, adjusts claims based on json file contents')
    parser.add_argument('-q', '--qos', help='initial claim is a qos claim', action='store_true')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args()

    tuner_algorithm = args.tuner_algorithm
    output_file = args.output_file
    initial_claim = args.initial_claim
    qos = True if args.qos else False
    debug = True if args.debug else False

    signal.signal(signal.SIGINT, signal_handler)

    r = React(algorithm=tuner_algorithm, output_path=output_file, claim=initial_claim, qos=qos, debug=debug)
    processes = [r]
    r.start()

    if args.experiment_file:
        print('Working through exp file')
        with open(args.experiment_file, 'r') as f:
            exp = json.load(f)

        for event in exp['events']:
            print(f'Updating claim: {event["claim"]}')
            r.new_demand(event['qos'], event['claim'])
            time.sleep(event['duration'])

        print('Terminating react process')
        r.terminate()
        # r.join()
        print(r.exitcode)
        sys.exit()
    else:
        while True:
            pass


if __name__ == '__main__':
    main()
