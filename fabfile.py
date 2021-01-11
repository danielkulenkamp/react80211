#!/usr/bin python

import time
import os
import socket
import struct
import json
import random

import lsb_release_ex as lsb

from fabric import Connection
from fabric import task
from fabric.group import ThreadingGroup

from invoke import run

from patchwork.files import exists

from utils.conn_matrix import ConnMatrix
from experiment_descriptors import dynamic_exps, complete_exps, line_exps, star_exps

"""
For the fabric tasks, my convention here is to put the first argument as 'c'
if the task does NOT use the passed in connection object. If the task DOES use
the passed in connection object, it will be called 'conn'. 

You don't have to pass in a value for c, because the default value is None. 
"""


# TODO: Fix it so it grabs the user's name, rather than using mine for all
USERNAME = 'dkulenka'
PROJECT_PATH = '/groups/wall2-ilabt-iminds-be/react/react80211'
HOSTS = []
PYTHON_PATH = '/groups/wall2-ilabt-iminds-be/react/pyenv/versions/3.9.0/bin/python'

HOSTS_DRIVER = []
HOSTS_TX_POWER = []
HOSTS_IPS = {}


def set_hosts(host_file):
    global HOSTS
    global HOSTS_DRIVER
    global HOSTS_TX_POWER
    global HOSTS_IPS

    hosts_info_file = open(host_file, 'r').readlines()

    hosts_info=[]
    for i in hosts_info_file:
        if not i.startswith("#"):
            hosts_info.append(i)

    HOSTS = [i.split(',')[0] for i in hosts_info]
    HOSTS_DRIVER = [i.split(',')[1].replace("\n", "") for i in hosts_info]
    HOSTS_TX_POWER = [i.split(',')[2].replace("\n", "") for i in hosts_info]
    for host in HOSTS:
        ip_index = HOSTS.index(host)
        HOSTS_IPS[host] = f'192.168.0.{ip_index + 1}'

# set nodes
set_hosts('node_info.txt')


# TODO: See if you really need to install all of these dependencies?
@task
def install_python_deps(c):
    """Install python dependencies. """
    global HOSTS

    group = ThreadingGroup(*HOSTS)
    group.run("sudo apt-get update; sudo apt-get install -y python-scapy python-netifaces python-numpy python-flask")


@task
def set_tx_power(c, interface = 'wls33', tx_power = 1):
    """Sets tx_power for an interface. """
    global HOSTS

    group = ThreadingGroup(*HOSTS)
    group.run(f'sudo iwconfig {interface} txpower {tx_power}')


@task
def network(c, frequency = 2412, interface = 'wls33',
            rts = 'off', mac_address = 'aa:bb:cc:dd:ee:ff'):
    """Sets up ad-hoc network between the nodes. """
    global HOSTS
    global HOSTS_DRIVER
    global HOSTS_TX_POWER
    global HOSTS_IPS

    monitor_interface = 'mon0'

    for host in HOSTS:
        ip_index = HOSTS.index(host)
        print(HOSTS)
        print(HOSTS_DRIVER)
        driver = HOSTS_DRIVER[ip_index]
        tx_power = HOSTS_TX_POWER[ip_index]
        print(HOSTS_TX_POWER)

        # ip_addr = f'192.168.0.{ip_index + 1}'
        ip_addr = HOSTS_IPS[host]
        rate = 6
        essid = 'test'

        # find backports binary
        if '18' in lsb.get_distro_information()['RELEASE']:
            backports_str = '/groups/wall2-ilabt-iminds-be/react/backports/18/backports-cw-tuning/'
        elif '16' in lsb.get_distro_information()['RELEASE']:
            backports_str = '/groups/wall2-ilabt-iminds-be/react/backports/16/backports-cw-tuning/'
        else:
            raise ValueError("Unsupported OS version")

        # associate host
        conn = Connection(host)
        # conn.run(f'cd {backports_str}')

        # This command has to be together, in order for the kernel modules to load
        # it uses relative folders in the load.sh script, so we need to be inside
        # the backports patch folder
        conn.run(f'cd {backports_str};sudo ./load.sh', warn=True)

        conn.run(f'sudo iwconfig {interface} mode ad-hoc', warn=True)
        conn.run(f'sudo ifconfig {interface} {ip_addr} up', warn=True)
        conn.run(f'sudo iwconfig {interface} txpower {tx_power}dbm', warn=True)
        conn.run(f'sudo iwconfig {interface} rate {rate}M fixed', warn=True)
        conn.run(f'sudo iw dev {interface} ibss join {essid} {frequency} fixed-freq {mac_address}', warn=True)

        conn.run(f'sudo iw dev {interface} interface add {monitor_interface} type monitor')
        conn.run(f'sudo ifconfig {monitor_interface} up')
        conn.run(f'sudo iwconfig {interface} rts {rts}')


@task
def test_screen(c):
    """Tests to ensure screen is working among the nodes. """
    global HOSTS
    print(HOSTS)
    group = ThreadingGroup(*HOSTS)

    for conn in group:
        screen_start_session(conn, "test", "watch free -m")


@task
def stop_react_all(c):
    """Stops react on all nodes. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    for conn in group:
        stop_react(conn)


@task
def stop_react(conn):
    """Stops react on the node connected to with the given conn parameter. """
    screen_stop_session(conn, 'react')


@task
def run_react(conn, out_dir, tuner='salt', claim = 0.80, qos=False, filename=None, debug=False):
    """Starts react on the node connected to with the given conn parameter."""
    global PROJECT_PATH
    global PYTHON_PATH

    arguments = [tuner, f'{out_dir}/react.csv', str(claim)]

    if filename:
        arguments.append('-e')
        arguments.append(filename)

    if qos:
        arguments.append('--qos')

    if debug:
        arguments.append('--debug')

    react_path = os.path.join(PROJECT_PATH, 'testbed')

    stop_react(conn)

    executable_path = f"sudo {PYTHON_PATH} -u {react_path}/react.py {' '.join(arguments)}"
    print(executable_path)
    screen_start_session(conn, 'react', executable_path)


# TODO: Test and ensure the cr tuning works (if you need to, of course)
@task
def stop_cr_tuning(c):
    """Stops cr tuning algorithm on all nodes. Untested!"""
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    for conn in group:
        screen_stop_session(conn, 'cr_tuning')


@task
def run_cr_tuning(c, out_dir = None):
    """Runs the cr tuning algorithm on all nodes. Untested!"""
    global HOSTS
    global PYTHON_PATH
    global PROJECT_PATH

    group = ThreadingGroup(*HOSTS)

    for conn in group:
        if out_dir is None:
            # Don't use unique output directory (this case is just for testing)
            out_dir = make_out_directory(conn, unique=False)

        stop_cr_tuning(conn)

        executable_path = f"sudo {PYTHON_PATH} -u {PROJECT_PATH}/helpers/cr_tuning.py {out_dir}/react.csv || cat"

        screen_start_session(conn, 'cr_tuning', executable_path)
        # screen_start_session(conn, 'cr_tuning',
        #         'sudo python3 -u {}/helpers/cr_tuning.py {}/react.csv'.format(
        #             project_path, out_dir) +
        #         ' || cat') # "or error, cat" keeps screen open for stdout inspection

################################################################################
# misc


def dot2long(ip):
    """Converts human readable IP address to a bit-packed machine format. """
    return struct.unpack("!L", socket.inet_aton(ip))[0]


def long2dot(ip):
    """Converts bit-packet machine IP address to human readable format. """
    return socket.inet_ntoa(struct.pack('!L', ip))


@task
def get_mac(conn, dev='wls33'):
    """Gets the mac address of the device connected to with the given conn object. """
    global PYTHON_PATH
    cmd = f"{PYTHON_PATH} -c 'from netifaces import *; print(ifaddresses(\"{dev}\")[17][0][\"addr\"])'"
    result = conn.run(cmd).stdout.splitlines()[0]

    return result


@task
def get_my_ip(conn, dev = 'wls33'):
    """Gets the IP address of the device connected to with the given conn object. """
    global PYTHON_PATH
    cmd = f"{PYTHON_PATH} -c 'from netifaces import *; print(ifaddresses(\"{dev}\")[AF_INET][0][\"addr\"])'"
    result = conn.run(cmd).stdout.splitlines()[0]
    return result


@task
def time_sync(c):
    """Synchronizes the time among the nodes. This is imprecise, PTPd is better for precision. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    group.run('sudo service ntp stop')
    group.run('sudo ntpdate time.nist.gov')


@task
def reboot(c):
    """Reboots all nodes. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    group.run('sudo reboot')


@task
def start_test_screens(c):
    """Starts screens for react, mgen, and tshark on all nodes"""
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    group.run('screen -S mgen', pty=False)
    group.run('screen -S react', pty=False)
    group.run('screen -S tshark', pty=False)

@task
def yobooyathere(c):
    """A cheeky way to make sure you are connected to all the nodes. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    group.run(':')
    group.run('echo hi')


@task
def screen_start_session(conn, name, cmd):
    """Start a screen session with the given command on the node connected to with the given conn object. """
    conn.run(f'screen -S {name} -dm bash -c "{cmd}"', pty=False)


@task
def screen_stop_session(conn, name, interrupt = False):
    """Stop a screen session with the given name on the node connected to with the given conn object. """
    if interrupt:
        conn.run(f'screen -S {name} -p 0 -X stuff " "', warn=True)
    else:
        conn.run(f'screen -S {name} -X quit', warn=True)


@task
def screen_stop_all(c):
    """Stop all screen sessions on all nodes, except for PTPd sessions. """
    global HOSTS

    for host in HOSTS:
        conn = Connection(host)
        conn.run('screen -wipe', warn=True)

        result = conn.run('ls /var/run/screen/S-$(whoami)')
        sessions = result.stdout.strip().split()

        for name in sessions:
            if name.split('.')[1] != 'running' and name.split('.')[1] != 'ptpd' and name.split('.')[1] != 'tshark':
                screen_stop_session(conn, name)


@task
def iperf_start_servers(c):
    """Starts UDP and TCP iperf servers on all of the nodes. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    for conn in group:
        screen_start_session(conn, 'iperf_server_udp', 'iperf -s -u')
        screen_start_session(conn, 'iperf_server_tcp', 'iperf -s')


@task
def mgen_start_stream(conn, conn_matrix, exp_name=''):
    filename = 'exp_script.mgen'
    # for server in conn_matrix.links(get_my_ip(conn)):
    server = conn_matrix.links(get_my_ip(conn))
    file_contents = f'0.0 ON 1 UDP DST {server[0]}/4001 POISSON [6000 1024]\n300.0 OFF 1\n'
    with open(filename, 'w') as f:
        f.write(file_contents)
    conn.put(filename)

    cmd = f'mgen input {filename}'
    screen_start_session(conn, 'mgen', cmd)


@task
def mgen_stop_all(c):
    """Stops all mgen clients on all of the nodes. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    for conn in group:
        screen_stop_session(conn, 'mgen', interrupt=True)
        screen_stop_session(conn, 'mgen_server', interrupt=True)


@task
def mgen_start_server(conn, host_out_dir):
    cmd = f"mgen event 'listen udp 4001' output {host_out_dir}/{get_my_ip(conn)}-mgen-log.drc"
    screen_start_session(conn, 'mgen_server', cmd)


@task
def iperf_start_clients(conn, host_out_dir, conn_matrix,
                        tcp = False):
    """Starts iperf clients on the nodes. It uses the passed ConnMatrix to determine which IP address to send to. """
    # for server in conn_matrix.links(get_my_ip(conn)):
    server = conn_matrix.links(get_my_ip(conn))
    print(server)
    print(f'conn.host: {conn.host}')
    print(server)
    cmd = 'iperf -c {}'.format(server[0])
    if not tcp:
        cmd += ' -u -b {}'.format(server[1])
    cmd += ' -t -1 -i 1 -yC'

    # Use -i (ignore signals) so that SIGINT propagted up pipe to iperf
    cmd += ' | tee -i {}/{}.csv'.format(host_out_dir, server[0])
    print(f'cmd: {cmd}')
    screen_start_session(conn, 'iperf_client', cmd)


@task
def iperf_test(c):
    """Tests iperf on one of the nodes. """
    global USERNAME
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.3', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.4', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.1', '6Mbps')

    for conn in group:
        iperf_start_clients(conn, f"/users/{USERNAME}/", cm)


@task
def iperf_stop_clients(c):
    """Stops all iperf clients on all of the nodes. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    for conn in group:
        screen_stop_session(conn, 'iperf_client', interrupt=True)


@task
def make_out_directory(conn, out_dir = '/groups/wall2-ilabt-iminds-be/react/data/test',
                       trial_dir = None, unique = True):
    """Makes an output directory at the given location. Does not overwrite directories,
    instead will increment the counter and create a new directory each time called. """
    expand_user_cmd = f"python -c 'import os; print(os.path.expanduser(\"{out_dir}\"))'"
    out_dir = run(expand_user_cmd).stdout.splitlines()[0]

    i = 0
    while True:
        sub_directories = [out_dir, '{:03}'.format(i)]

        # subdirs = []
        # subdirs.append(out_dir)
        # subdirs.append('{:03}'.format(i))
        if trial_dir is not None:
            sub_directories.append(trial_dir)
        sub_directories.append(conn.host)

        host_out_dir = '/'.join(sub_directories)

        if not unique or not(exists(conn, path=host_out_dir, runner=None)):
            break

        i += 1

    print(host_out_dir)
    conn.run(f'mkdir -p {host_out_dir}')
    return host_out_dir


@task
def install_mgen(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    group.run('sudo apt-get install mgen')


@task
def reset_netifaces(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    group.run('sudo ifconfig wls33 down')
    group.run('sudo ifconfig wls33 up')


@task
def setup_tc(c, iface='wls33', initial_rate='6mbit'):
    global HOSTS

    dst_nodes = [
        '192.168.0.1',
        '192.168.0.2',
        '192.168.0.3',
        '192.168.0.4',
    ]

    commands = [
        f'sudo tc qdisc add dev {iface} root handle 1:0 htb default 30',
        f'sudo tc class add dev {iface} parent 1:0 classid 1:1 htb rate {initial_rate}',
    ]
    for node in dst_nodes:
        commands.append(
            f'sudo tc filter add dev {iface} protocol all parent 1: u32 match ip dst {node} flowid 1:1'
        )

    for host in HOSTS:
        for command in commands:
            with Connection(host) as conn:
                conn.run(command, warn=True)


@task
def setup(c):
    """Sets up all of the nodes. Includes time synchronization, creating the ad-hoc network,
    and starting iperf servers. """
    screen_stop_all(c)
    time_sync(c)
    reset_netifaces(c)
    network(c, frequency = 5180)
    setup_tc(c)
    iperf_start_servers(c)
    install_mgen(c)


@task
def reset_shapers(c, iface='wls33', default_max=6):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    for conn in group:
        conn.run(f'sudo tc class change dev {iface} parent 1:0 classid 1:1 htb rate {default_max}mbit')

@task
def stop_exp(c):
    """Stops experiment. Involves stopping all screen sessions and restarting iperf servers. """
    screen_stop_all(c)
    iperf_start_servers(c)
    mgen_stop_all(c)
    reset_shapers(c)


@task
def graph_test(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    out_dirs = {}
    for conn in group:
        out_dirs[conn.host] = make_out_directory(conn,
                                                 f'/groups/wall2-ilabt-iminds-be/react/data/{graph_test.__name__}')

    for conn in group:
        nodes = [i for i in range(len(group))]
        random.shuffle(nodes)
        print(nodes)

        cmd = 'ping -c 100 -I wls33 192.168.0.{0} > {1}/192.168.0.{0}'
        for n in nodes:
            conn.run(cmd.format(n+1, out_dirs[conn.host]), warn=True)




@task
def update_test(c, use):
    """Experiment for testing the updates to react. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    assert (use == "dot" or use == "salt" or use == "renew")

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')

    out_dirs = {}

    for conn in group:
        out_dirs[conn.host] = make_out_directory(conn,
                                                 f'/groups/wall2-ilabt-iminds-be/react/data/{update_test.__name__}',
                                                 trial_dir=use)

    print("starting Streams")
    for conn in group:
        mgen_start_streams(conn, cm)
        # iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)

    print("Starting REACT")
    for conn in group:
        run_react(conn, out_dir=out_dirs[conn.host], tuner=use)

    print("Collecting measurements")

    time.sleep(120)

    print('Stopping experiment')
    stop_exp(c)


@task
def variable_react_complete(c):
    """Experiment for testing updates, with different claims. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.3', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.4', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.1', '6Mbps')

    experiments = [
        # {
        #     'zotacC2.wilab2.ilabt.iminds.be': 0.05,
        #     'zotacC3.wilab2.ilabt.iminds.be': 1.0,
        #     'zotacB2.wilab2.ilabt.iminds.be': 1.0,
        #     'zotacB3.wilab2.ilabt.iminds.be': 1.0,
        # },
        {
            'zotacB2.wilab2.ilabt.iminds.be': 0.05,
            'zotacB3.wilab2.ilabt.iminds.be': 0.2,
            'zotacC2.wilab2.ilabt.iminds.be': 0.2,
            'zotacC3.wilab2.ilabt.iminds.be': 1.0,
        },
        # {
        #     'zotacC2.wilab2.ilabt.iminds.be': 1.0,
        #     'zotacC3.wilab2.ilabt.iminds.be': 0.05,
        #     'zotacB2.wilab2.ilabt.iminds.be': 0.2,
        #     'zotacB3.wilab2.ilabt.iminds.be': 0.2,
        # },
        # {
        #     'zotacC2.wilab2.ilabt.iminds.be': 0.2,
        #     'zotacC3.wilab2.ilabt.iminds.be': 1.0,
        #     'zotacB2.wilab2.ilabt.iminds.be': 0.05,
        #     'zotacB3.wilab2.ilabt.iminds.be': 0.2,
        # },
        # {
        #     'zotacC2.wilab2.ilabt.iminds.be': 0.2,
        #     'zotacC3.wilab2.ilabt.iminds.be': 0.2,
        #     'zotacB2.wilab2.ilabt.iminds.be': 1.0,
        #     'zotacB3.wilab2.ilabt.iminds.be': 0.05,
        # },
        # {
        #     'zotacC2.wilab2.ilabt.iminds.be': 0.05,
        #     'zotacC3.wilab2.ilabt.iminds.be': 0.05,
        #     'zotacB2.wilab2.ilabt.iminds.be': 0.5,
        #     'zotacB3.wilab2.ilabt.iminds.be': 0.5,
        # },
        # {
        #     'zotacC2.wilab2.ilabt.iminds.be': 0.15,
        #     'zotacC3.wilab2.ilabt.iminds.be': 0.05,
        #     'zotacB2.wilab2.ilabt.iminds.be': 0.75,
        #     'zotacB3.wilab2.ilabt.iminds.be': 0.5,
        # },
    ]

    i = 1
    for exp in experiments:
        for use in ['salt']:
            out_dirs = {}
            for conn in group:
                out_dirs[conn.host] = \
                    make_out_directory(
                        conn,
                        f'/groups/wall2-ilabt-iminds-be/react/data/test-{variable_react_complete.__name__}-{i}',
                        trial_dir=use
                    )

            print('starting streams')
            for conn in group:
                iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)
                # mgen_start_streams(conn, cm)

            print('Starting REACT')

            for conn in group:
                run_react(conn, out_dir=out_dirs[conn.host], tuner=use, claim=exp[conn.host], debug=True)

            print('Collecting Measurements')
            time.sleep(120)
            print('Stopping experiment')
            stop_exp(c)
        i += 1


@task
def variable_react_star(c):
    """Experiment for testing variable REACT on a star topology. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.4')
    cm.add('192.168.0.2', r'192.168.0.4')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')

    experiments = [
        {
            'zotacJ6.wilab2.ilabt.iminds.be': 1.0,
            'zotacD6.wilab2.ilabt.iminds.be': 1.0,
            'zotacH1.wilab2.ilabt.iminds.be': 1.0,
            'zotacG4.wilab2.ilabt.iminds.be': 1.0,
        },
        {
            'zotacJ6.wilab2.ilabt.iminds.be': 1.0,
            'zotacD6.wilab2.ilabt.iminds.be': 0.5,
            'zotacH1.wilab2.ilabt.iminds.be': 0.2,
            'zotacG4.wilab2.ilabt.iminds.be': 0.1,
        },
        {
            'zotacJ6.wilab2.ilabt.iminds.be': 1.0,
            'zotacD6.wilab2.ilabt.iminds.be': 1.0,
            'zotacH1.wilab2.ilabt.iminds.be': 0.3,
            'zotacG4.wilab2.ilabt.iminds.be': 0.2,
        },
        {
            'zotacJ6.wilab2.ilabt.iminds.be': 1.0,
            'zotacD6.wilab2.ilabt.iminds.be': 0.4,
            'zotacH1.wilab2.ilabt.iminds.be': 0.1,
            'zotacG4.wilab2.ilabt.iminds.be': 0.1,
        },

    ]

    i = 0
    for exp in experiments:
        for use in ['dot', 'salt']:
            out_dirs = {}
            for conn in group:
                out_dirs[conn.host] = \
                    make_out_directory(
                        conn,
                        f'/groups/wall2-ilabt-iminds-be/react/data/{variable_react_star.__name__}-{i}',
                        trial_dir=use
                    )

            print('starting streams')
            for conn in group:
                iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)

            print('Starting REACT')

            for conn in group:
                run_react(conn, out_dir=out_dirs[conn.host], tuner=use, claim=exp[conn.host])

            print('Collecting Measurements')
            time.sleep(120)
            print('Stopping experiment')
            stop_exp(c)
        i += 1


@task
def update_test_diff(c, use):
    """Experiment for testing the updates to react. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)
    assert (use == "dot" or use == "salt" or use == "renew")

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.1')
    cm.add('192.168.0.4', r'192.168.0.1')

    out_dirs = {}

    for conn in group:
        out_dirs[conn.host] = make_out_directory(conn,
                                                 f'/groups/wall2-ilabt-iminds-be/react/data/{update_test_diff.__name__}',
                                                 trial_dir=use)

    print("starting Streams")
    for conn in group:
        iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)

    print("Starting REACT")
    for conn in group:
        if conn.host == 'zotacC2.wilab2.ilabt.iminds.be':
            run_react(conn, out_dir=out_dirs[conn.host], tuner=use, claim=0.05)
        else:
            run_react(conn, out_dir=out_dirs[conn.host], tuner=use)

    print("Collecting measurements")

    time.sleep(120)

    print('Stopping experiment')
    stop_exp(c)


@task
def update_test_qos(c, tuner):
    """Experiment for testing QoS functionality of react. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    assert (tuner == "dot" or tuner == "salt" or tuner == 'renew')

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.3', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.4', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.1', '6Mbps')

    out_dirs = {}

    for conn in group:
        out_dirs[conn.host] = make_out_directory(conn, '/groups/wall2-ilabt-iminds-be/react/data/update_test_qos',
                                                 trial_dir=tuner)

    print("starting Streams")
    for conn in group:
        iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)

    print('starting REACT')
    for conn in group:
        if conn.host == 'zotacB3.wilab2.ilabt.iminds.be':
            run_react(conn, out_dirs[conn.host], tuner, claim=0.5, qos=True, debug=True)
        else:
            run_react(conn, out_dirs[conn.host], tuner, debug=True)

    print("Collecting measurements")

    time.sleep(120)

    print('Stopping Experiment')
    stop_exp(c)


@task
def test_react(c, use):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    assert (use == "dot" or use == "salt" or use == "renew")

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.3', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.4', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.1', '6Mbps')

    out_dirs = {}

    for conn in group:
        out_dirs[conn.host] = make_out_directory(conn, '/groups/wall2-ilabt-iminds-be/react/data/test_react',
                                                 trial_dir=use)

    print('starting REACT')
    for conn in group:
        if conn.host == 'zotacB3.wilab2.ilabt.iminds.be':
            run_react(conn, out_dirs[conn.host], use, claim=1.0)
        elif conn.host == 'zotacF2.wilab2.ilabt.iminds.be':
            run_react(conn, out_dirs[conn.host], use, claim=0.25)
        else:
            run_react(conn, out_dirs[conn.host], use, claim=0.25)

    print('Waiting for REACT to converge')
    time.sleep(120)

    print('Stopping Experiment')
    stop_exp(c)


@task
def dynamic_react_complete(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.3', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.4', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.1', '6Mbps')

    for exp in dynamic_exps.experiments:
        for use in ['salt']:
            out_dirs = {}
            for conn in group:
                out_dirs[conn.host] = \
                    make_out_directory(
                        conn,
                        f'/groups/wall2-ilabt-iminds-be/react/data/{dynamic_react_complete.__name__}-{exp["exp_name"]}',
                        trial_dir=use
                    )

            for conn in group:
                filename = f'{exp["exp_name"]}-{conn.host}.txt'
                with open(filename, 'w') as f:
                    json.dump(exp[conn.host], f)

                conn.put(filename)

            print('starting streams')
            for conn in group:
                iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)

            print('starting REACT')
            for conn in group:
                filename = f'{exp["exp_name"]}-{conn.host}.txt'
                run_react(conn, out_dirs[conn.host], tuner=use, claim=1.0, qos=False, filename=filename, debug=True)

            print(f'running experiment {exp["exp_name"]}')
            time.sleep(exp["duration"])

            print(f'stopping experiment {exp["exp_name"]}')
            stop_exp(c)


@task
def run_exps_complete(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.3', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.4', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.1', '6Mbps')

    for exp in complete_exps.experiments:
        out_dirs = {}
        for conn in group:
            out_dirs[conn.host] = \
                make_out_directory(
                    conn,
                    f'/groups/wall2-ilabt-iminds-be/react/data/{run_exps_complete.__name__}-mgen-{exp["exp_name"]}',
                    trial_dir=exp['tuner']
                )

        for conn in group:
            filename = f'{exp["exp_name"]}-{conn.host}.txt'
            with open(filename, 'w') as f:
                json.dump(exp[conn.host], f)

            conn.put(filename)

        print('starting servers')
        for conn in group:
            # iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)
            mgen_start_server(conn, out_dirs[conn.host])

        print('starting streams')
        for conn in group:
            mgen_start_stream(conn, cm)

        print('starting REACT')
        for conn in group:
            filename = f'{exp["exp_name"]}-{conn.host}.txt'
            run_react(
                conn,
                out_dirs[conn.host],
                tuner=exp['tuner'],
                claim=1.0,
                qos=False,
                filename=filename,
                debug=False)

        print(f'running experiment {exp["exp_name"]}')
        time.sleep(exp["duration"])

        print(f'stopping experiment {exp["exp_name"]}')
        stop_exp(c)


@task
def run_exps_line(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.1', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.4', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.3', '6Mbps')

    for exp in line_exps.experiments:
        out_dirs = {}
        for conn in group:
            out_dirs[conn.host] = \
                make_out_directory(
                    conn,
                    f'/groups/wall2-ilabt-iminds-be/react/data/{run_exps_line.__name__}-mgen-{exp["exp_name"]}',
                    trial_dir=exp['tuner']
                )

        for conn in group:
            filename = f'{exp["exp_name"]}-{conn.host}.txt'
            with open(filename, 'w') as f:
                json.dump(exp[conn.host], f)

            conn.put(filename)

        print('starting servers')
        for conn in group:
            # iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)
            mgen_start_server(conn, out_dirs[conn.host])

        print('starting streams')
        for conn in group:
            mgen_start_stream(conn, cm)

        print('starting REACT')
        for conn in group:
            filename = f'{exp["exp_name"]}-{conn.host}.txt'
            run_react(
                conn,
                out_dirs[conn.host],
                tuner=exp['tuner'],
                claim=1.0,
                qos=False,
                filename=filename,
                debug=False)

        print(f'running experiment {exp["exp_name"]}')
        time.sleep(exp["duration"])

        print(f'stopping experiment {exp["exp_name"]}')
        stop_exp(c)


@task
def run_exps_star(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.5', '6Mbps')
    cm.add('192.168.0.2', r'192.168.0.5', '6Mbps')
    cm.add('192.168.0.3', r'192.168.0.5', '6Mbps')
    cm.add('192.168.0.4', r'192.168.0.5', '6Mbps')
    cm.add('192.168.0.5', r'192.168.0.1', '6Mbps')

    for exp in star_exps.experiments:
        out_dirs = {}
        for conn in group:
            out_dirs[conn.host] = \
                make_out_directory(
                    conn,
                    f'/groups/wall2-ilabt-iminds-be/react/data/{run_exps_star.__name__}-{exp["exp_name"]}',
                    trial_dir=exp['tuner']
                )

        for conn in group:
            filename = f'{exp["exp_name"]}-{conn.host}.txt'
            with open(filename, 'w') as f:
                json.dump(exp[conn.host], f)

            conn.put(filename)

        print('starting streams')
        for conn in group:
            iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)

        print('starting REACT')
        for conn in group:
            filename = f'{exp["exp_name"]}-{conn.host}.txt'
            run_react(
                conn,
                out_dirs[conn.host],
                tuner=exp['tuner'],
                claim=1.0,
                qos=False,
                filename=filename,
                debug=False)

        print(f'running experiment {exp["exp_name"]}')
        time.sleep(exp["duration"])

        print(f'stopping experiment {exp["exp_name"]}')
        stop_exp(c)


@task
def mgen_test(c):
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    out_dirs = {}
    for conn in group:
        out_dirs[conn.host] = \
            make_out_directory(
                conn,
                f'/groups/wall2-ilabt-iminds-be/react/data/{mgen_test.__name__}-test',
                trial_dir='salt'
            )

    for conn in group:
        mgen_start_server(conn, out_dirs[conn.host])

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2', '6M')
    cm.add('192.168.0.2', r'192.168.0.3', '6M')
    cm.add('192.168.0.3', r'192.168.0.4', '6M')
    cm.add('192.168.0.4', r'192.168.0.1', '6M')

    for conn in group:
        mgen_start_stream(conn, cm)


