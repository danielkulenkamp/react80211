#!/usr/bin python

import time
import os
import socket
import struct

import lsb_release_ex as lsb

from fabric import Connection
from fabric import task
from fabric.group import ThreadingGroup

from invoke import run

from patchwork.files import exists

from utils.conn_matrix import ConnMatrix

"""
For the fabric tasks, my convention here is to put the first argument as 'c'
if the task does NOT use the passed in connection object. If the task DOES use
the passed in connection object, it will be called 'conn'. 

You don't have to pass in a value for c, because the default value is None. 
"""


# TODO: Fix it so it grabs the user's name, rather than using mine for all
USERNAME = 'dkulenka'
PROJECT_PATH = '/groups/wall2-ilabt-iminds-be/react/updating/react80211'
HOSTS = []
PYTHON_PATH = '/groups/wall2-ilabt-iminds-be/react/pyenv/versions/3.9.0/bin/python'

HOSTS_DRIVER = []
HOSTS_TX_POWER = []


def set_hosts(host_file):
    global HOSTS
    global HOSTS_DRIVER
    global HOSTS_TX_POWER

    hosts_info_file = open(host_file, 'r').readlines()

    hosts_info=[]
    for i in hosts_info_file:
        if not i.startswith("#"):
            hosts_info.append(i)

    HOSTS = [i.split(',')[0] for i in hosts_info]
    HOSTS_DRIVER = [i.split(',')[1].replace("\n", "") for i in hosts_info]
    HOSTS_TX_POWER = [i.split(',')[2].replace("\n", "") for i in hosts_info]

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

    monitor_interface = 'mon0'

    for host in HOSTS:
        ip_index = HOSTS.index(host)
        print(HOSTS)
        print(HOSTS_DRIVER)
        driver = HOSTS_DRIVER[ip_index]
        tx_power = HOSTS_TX_POWER[ip_index]
        print(HOSTS_TX_POWER)

        ip_addr = f'192.168.0.{ip_index + 1}'
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
def run_react(conn, out_dir=None, tuner='salt', beta=0.6,
              k = 500, claim = 0.80, pre_allocation=0, qos=False,
              interface='wls33'):
    """Starts react on the node connected to with the given conn parameter."""
    global PROJECT_PATH
    global PYTHON_PATH

    # arguments = ['-i', interface, '-t', '0.1', '-r', '6000', '-b', str(beta), '-k', str(k)]
    arguments = ['-t', '0.1']

    if qos:
        arguments.append('-q')
        arguments.append('True')

    arguments.append('-c')
    arguments.append(str(claim))

    # Without a tuner REACT is disabled and we just collect airtime data
    if tuner == 'salt' or tuner == 'renew':
        arguments.append('-e')
        arguments.append(tuner)

    arguments.append('-o')
    if out_dir is None:
        # Don't use unique output directory (this case is just for testing)
        out_dir = make_out_directory(conn, unique=False)
    arguments.append(f'{out_dir}/react.csv')

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
            if name.split('.')[1] != 'running' and name.split('.')[1] != 'ptpd':
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
def iperf_start_clients(conn, host_out_dir, conn_matrix,
                        tcp = False, rate = '50MMbps'):
    """Starts iperf clients on the nodes. It uses the passed ConnMatrix to determine which IP address to send to. """
    for server in conn_matrix.links(get_my_ip(conn)):
        cmd = 'iperf -c {}'.format(server)
        if not tcp:
            cmd += ' -u -b {}'.format(rate)
        cmd += ' -t -1 -i 1 -yC'

        # Use -i (ignore signals) so that SIGINT propagted up pipe to iperf
        cmd += ' | tee -i {}/{}.csv'.format(host_out_dir, server)

        screen_start_session(conn, 'iperf_client', cmd)


@task
def iperf_test(c):
    """Tests iperf on one of the nodes. """
    global HOSTS
    group = ThreadingGroup(*HOSTS)

    cm = ConnMatrix()
    cm.add('192.168.0.1', '192.168.0.2')
    cm.add('192.168.0.2', 'NONE')

    for conn in group:
        iperf_start_clients(conn, "/users/{username}/", cm)


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
def setup(c):
    """Sets up all of the nodes. Includes time synchronization, creating the ad-hoc network,
    and starting iperf servers. """
    screen_stop_all(c)
    time_sync(c)
    network(c, frequency = 5180)
    iperf_start_servers(c)


@task
def stop_exp(c):
    """Stops experiment. Involves stopping all screen sessions and restarting iperf servers. """
    screen_stop_all(c)
    iperf_start_servers(c)


@task
def update_test(c, use):
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
                                                 f'/groups/wall2-ilabt-iminds-be/react/data/{update_test.__name__}',
                                                 trial_dir=use)

    print("starting Streams")
    for conn in group:
        iperf_start_clients(conn, out_dirs[conn.host], cm, tcp=False)

    print("Starting REACT")
    for conn in group:
        run_react(conn, out_dir=out_dirs[conn.host], tuner=use)

    print("Collecting measurements")

    time.sleep(120)

    print('Stopping experiment')
    stop_exp(c)


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
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')

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
            run_react(conn, out_dirs[conn.host], tuner, claim=0.5, qos=True)
        else:
            run_react(conn, out_dirs[conn.host], tuner)

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
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')

    out_dirs = {}

    for conn in group:
        out_dirs[conn.host] = make_out_directory(conn, '/groups/wall2-ilabt-iminds-be/react/data/test_react',
                                                 trial_dir=use)

    print('starting REACT')
    for conn in group:
        run_react(conn, out_dirs[conn.host], use)

    print('Waiting for REACT to converge')
    time.sleep(20)

    print('Stopping Experiment')
    stop_exp(c)
