#!/users/dkulenka/.pyenv/shims/python

import time
import os
import random
from distutils.util import strtobool
import json

import fabric.api as fab
from fabric.contrib.files import exists

from utils.conn_matrix import ConnMatrix
from utils.username import get_username

fab.env.user = 'dkulenka'
project_path = os.path.join('/groups/wall2-ilabt-iminds-be/react/old_react/react80211')

python_path = '/users/dkulenka/.pyenv/shims/python'
hosts_driver = []
hosts_txpower = []

def set_hosts(host_file):
    #fab.env.hosts = open(host_file, 'r').readlines()
    global hosts_txpower;
    hosts_info_file = open(host_file, 'r').readlines()
    hosts_info=[];
    hosts_driver=[];
    for i in hosts_info_file:
        if not i.startswith("#"):
            hosts_info.append(i);
    fab.env.hosts = [i.split(',')[0] for i in hosts_info]
    hosts_driver= [i.split(',')[1].replace("\n", "") for i in hosts_info]
    print hosts_driver
    hosts_txpower= [i.split(',')[2].replace("\n", "") for i in hosts_info]
    return hosts_driver

#---------------------
#SET NODES
hosts_driver = set_hosts('node_info.txt')

@fab.task
@fab.parallel
def install_python_deps():
    fab.sudo("apt-get install -y python-scapy python-netifaces python-numpy python-flask")

@fab.task
@fab.parallel
# Ad-hoc node association
#echo "usage $0 <iface> <essid> <freq> <power> <rate> <ip> <mac> <reload[1|0]>"
def associate(driver,iface,essid,freq,txpower,rate,ip_addr,mac_address="aa:bb:cc:dd:ee:ff",skip_reload=False,rts='off'):
    # Load kernel modules
    fab.sudo('cd /groups/wall2-ilabt-iminds-be/react/backports/16-new/backports-cw-tuning && ./load.sh')

    # Setup wireless interfaces
    with fab.settings(warn_only=True):
            fab.run('sudo iwconfig {0} mode ad-hoc; sudo ifconfig {0} {5} up;sudo iwconfig {0} txpower {3}dbm; sudo iwconfig {0} rate {4}M fixed;sudo iw dev {0} ibss join {1} {2} fixed-freq {6}'.format(iface,essid,freq,txpower,rate,ip_addr,mac_address))
            iface_mon='mon0';
            fab.sudo('iw dev {0} interface add {1} type monitor'.format(iface,iface_mon));
            fab.sudo('ifconfig {0} up'.format(iface_mon));
            fab.run('sudo iwconfig {0} rts {1}'.format(iface,rts))

@fab.task
@fab.parallel
def set_txpower(txpower):
    fab.run('sudo iwconfig wls33 txpower {0}'.format(txpower))

@fab.task
#setup network, ad-hoc association
def network(freq=2412,host_file=''):
    global hosts_txpower

    #search my host
    i_ip=fab.env.hosts.index(fab.env.host)
    print fab.env.hosts
    print hosts_driver
    driver=hosts_driver[i_ip];
    txpower=hosts_txpower[i_ip]
    print hosts_txpower
    fab.execute(associate,driver,'wls33','test',freq,txpower,6,'192.168.0.{0}'.format(i_ip+1),'aa:bb:cc:dd:ee:ff',skip_reload=False,rts='250',hosts=[fab.env.hosts[i_ip]])

@fab.task
@fab.parallel
def stop_react():
    screen_stop_session('react')

@fab.task
@fab.parallel
def stop_react2():
    with fab.settings(warn_only=True):
        fab.sudo("pid=$(pgrep react.py) && kill -9 $pid")

@fab.task
@fab.parallel
def run_react(out_dir=None, tuner='new', beta=0.6, k=500, capacity=.80,
        prealloc=0):
    args = []

    args.append('-i')
    args.append('wls33')

    args.append('-t')
    args.append('0.1')

    args.append('-r')
    args.append('6000')

    args.append('-b')
    args.append(str(beta))

    args.append('-k')
    args.append(str(k))

    args.append('-c')
    args.append(str(capacity))

    args.append('-p')
    args.append(str(prealloc))

    # Without a tuner REACT is disabled and we just collect airtime data
    if tuner == 'new' or tuner == 'old':
        args.append('-e')
        args.append(tuner)

    args.append('-o')
    if out_dir is None:
        # Don't use unique output directory (this case is just for testing)
        out_dir = makeout(unique=False)
    args.append('{}/react.csv'.format(out_dir))

    stop_react()
    screen_start_session('react',
            'sudo python2.7 -u {}/_react.py {}'.format(
                os.path.join(project_path, 'testbed'), 
                ' '.join(args)))

@fab.task
@fab.parallel
def run_react2(out_dir=None, enable_react=True):
    args = []

    args.append('-i')
    args.append('wls33')

    args.append('-t')
    args.append('0.1')

    args.append('-r')
    args.append('6000')

    if enable_react:
        args.append('-e')

    args.append('-o')
    if out_dir is None:
        out_dir = makeout()
    args.append(out_dir)

    stop_react2()
    fab.sudo('setsid {}/react.py {} &>~/react.{}.out </dev/null &'.format(
        project_path, ' '.join(args), fab.env.host), pty=False)


@fab.task
@fab.parallel
def stop_cr_tuning():
    screen_stop_session('cr_tuning')

@fab.task
@fab.parallel
def run_cr_tuning(out_dir=None):
    if out_dir is None:
        # Don't use unique output directory (this case is just for testing)
        out_dir = makeout(unique=False)

    stop_cr_tuning()
    screen_start_session('cr_tuning',
            'sudo python2.7 -u {}/helpers/cr_tuning.py {}/react.csv'.format(
                project_path, out_dir) +
            ' || cat') # "or error, cat" keeps screen open for stdout inspection

################################################################################
# misc

import socket
import struct

def dot2long(ip):
    return struct.unpack("!L", socket.inet_aton(ip))[0]

def long2dot(ip):
    return socket.inet_ntoa(struct.pack('!L', ip))

def get_my_mac(dev='wls33'):
    cmd = 'python -c' \
            " 'from netifaces import *;" \
            ' print ifaddresses("{}")[17][0]["addr"]\''
    return fab.run(cmd.format(dev))

def get_my_ip(dev='wls33'):
    cmd = 'python -c' \
            " 'from netifaces import *;" \
            ' print ifaddresses("{}")[AF_INET][0]["addr"]\''
    return fab.run(cmd.format(dev))

@fab.task
@fab.parallel
def time_sync():
    fab.sudo('service ntp stop')
    fab.sudo('ntpdate time.nist.gov')

@fab.task
@fab.parallel
def rm_proxy():
    fab.sudo('rm -f /etc/apt/apt.conf.d/01proxy')

@fab.task
@fab.parallel
def yobooyathere():
    fab.run(':')

################################################################################
# screen

def screen_start_session(name, cmd):
    fab.run('screen -S {} -dm bash -c "{}"'.format(name, cmd), pty=False)

def screen_stop_session(name, interrupt=False):
    with fab.settings(warn_only=True):
        if interrupt:
            fab.run('screen -S {} -p 0 -X stuff ""'.format(name))
        else:
            fab.run('screen -S {} -X quit'.format(name))

def screen_list():
    return fab.run('ls /var/run/screen/S-$(whoami)').split()

@fab.task
def screen_stop_all():
    with fab.settings(warn_only=True):
        fab.run('screen -wipe')

    sessions = screen_list()
    for name in sessions:
        screen_stop_session(name)

################################################################################
# iperf and roadtrip

@fab.task
def iperf_start_servers():
    screen_start_session('iperf_server_udp', 'iperf -s -u')
    screen_start_session('iperf_server_tcp', 'iperf -s')

@fab.task
def iperf_start_clients(host_out_dir, conn_matrix, tcp=False, rate='1G'):
    for server in conn_matrix.links(get_my_ip()):
        cmd = 'iperf -c {}'.format(server)
        if not(tcp):
            cmd += ' -u -b {}'.format(rate)
        cmd += ' -t -1 -i 1 -yC'

        # Use -i (ignore signals) so that SIGINT propagted up pipe to iperf
        cmd += ' | tee -i {}/{}.csv'.format(host_out_dir, server)

        screen_start_session('iperf_client', cmd)

@fab.task
def iperf_stop_clients():
    screen_stop_session('iperf_client', interrupt=True)

@fab.task
def roadtrip_start_servers():
    # Roadtrip listens for TCP and UDP at the same time by default
    screen_start_session('roadtrip_server', '~/bin/roadtrip -listen' \
            ' &>>~/data/{}_roadtrip.log'.format(fab.env.host))

@fab.task
def roadtrip_start_clients(host_out_dir, conn_matrix, tcp=False):
    for server in conn_matrix.links(get_my_ip()):
        args = []

        args.append('-address')
        args.append(server)

        if not(tcp):
            args.append('-udp')

        cmd = '~/bin/roadtrip {} 2>&1 | tee -i {}/roadtrip_{}.csv'.format(
                " ".join(args), host_out_dir, server)

        screen_start_session('roadtrip_client', cmd)

@fab.task
def roadtrip_stop_clients():
    screen_stop_session('roadtrip_client', interrupt=True)

################################################################################
# Multi-hop MAC address setup

def collect_ip2mac_map(ip2mac):
    ip2mac[dot2long(get_my_ip())] = get_my_mac()

def sudo_ip_neigh_add(ip, mac):
    if not(isinstance(ip, str)):
        ip = long2dot(ip)

    ip_neigh_add_cmd = 'ip neighbor add {} lladdr {} dev wls33 nud permanent'
    fab.sudo(ip_neigh_add_cmd.format(ip, mac))

def set_neighbors(ip2mac):
    low_neigh = None
    myip = dot2long(get_my_ip())
    high_neigh = None

    lower = []
    higher = []

    for ip in ip2mac.keys():
        if ip + 1 == myip:
            low_neigh = ip
        elif ip - 1 == myip:
            high_neigh = ip
        elif ip < myip:
            lower.append(ip)
        elif ip > myip:
            higher.append(ip)
        else:
            pass # ip == myip

    fab.sudo('sysctl -w net.ipv4.ip_forward=1')
    fab.sudo('ip link set dev wls33 arp off')
    fab.sudo('ip neigh flush dev wls33')

    if low_neigh is not None:
        sudo_ip_neigh_add(low_neigh, ip2mac[low_neigh])
        for ip in lower:
            sudo_ip_neigh_add(ip, ip2mac[low_neigh])

    if high_neigh is not None:
        sudo_ip_neigh_add(high_neigh, ip2mac[high_neigh])
        for ip in higher:
            sudo_ip_neigh_add(ip, ip2mac[high_neigh])

@fab.task
@fab.runs_once
def setup_multihop():
    ip2mac = {}
    fab.execute(collect_ip2mac_map, ip2mac)
    fab.execute(set_neighbors, ip2mac)

################################################################################
# Multi-hop Reservations

@fab.parallel
def res_server_kickoff(ip2mac):

    def get_if_in_ip2mac(ip):
        if ip in ip2mac:
            return long2dot(ip)
        else:
            return ""

    myip = dot2long(get_my_ip())
    n1 = get_if_in_ip2mac(myip - 1)
    n2 = get_if_in_ip2mac(myip + 1)
    myip = long2dot(myip)

    screen_start_session('res_server',
            'python2.7 -u' \
            ' {}/reservation/reservation_server.py {} {} {}' \
            ' &>>~/data/{}_res_server.log'.format(project_path, myip, n1, n2,
            fab.env.host))

@fab.task
@fab.runs_once
def res_server_start():
    ip2mac = {}
    fab.execute(collect_ip2mac_map, ip2mac)
    fab.execute(res_server_kickoff, ip2mac)

@fab.task
@fab.parallel
def res_server_stop():
    screen_stop_session('res_server')

################################################################################
# start/stop exps and make output dirs

@fab.task
@fab.parallel
def makeout(out_dir='/groups/wall2-ilabt-iminds-be/react/old_react/test', trial_dir=None, unique=True):
    expanduser_cmd = "python -c 'import os; print os.path.expanduser(\"{}\")'"
    out_dir = fab.run(expanduser_cmd.format(out_dir))

    i = 0
    while True:
        subdirs = []
        subdirs.append(out_dir)
        subdirs.append('{:03}'.format(i))
        if trial_dir is not None:
            subdirs.append(trial_dir)
        subdirs.append(fab.env.host)

        host_out_dir = '/'.join(subdirs)

        if not(unique) or not(exists(host_out_dir)):
            break

        i +=1

    fab.run('mkdir -p "{}"'.format(host_out_dir))
    return host_out_dir

@fab.task
@fab.parallel
def setup():
    rm_proxy()
    time_sync()
    install_python_deps()
    network(freq=5180)
    iperf_start_servers()
    roadtrip_start_servers()

@fab.task
@fab.parallel
def stop_exp():
    stop_react()
    stop_react2()
    iperf_stop_clients()
    res_server_stop()
    roadtrip_stop_clients()
    stop_cr_tuning()

################################################################################
# topos

def topo(tname, host_out_dir, tcp):
    cm = ConnMatrix()

    if tname == 'star':
        cm.add('192.168.0.1', r'192.168.0.5')
        cm.add('192.168.0.2', r'192.168.0.5')
        cm.add('192.168.0.3', r'192.168.0.5')
        cm.add('192.168.0.4', r'192.168.0.5')
        cm.add('192.168.0.5', r'NONE')
    elif tname == '3hop':
        cm.add('192.168.0.1', r'192.168.0.2')
        cm.add('192.168.0.2', r'192.168.0.3')
        cm.add('192.168.0.3', r'192.168.0.2')
        cm.add('192.168.0.4', r'192.168.0.3')
    elif tname == 'bae':
        cm.add('192.168.0.1', r'192.168.0.2')
        cm.add('192.168.0.2', r'192.168.0.3')
        cm.add('192.168.0.3', r'192.168.0.4')
        cm.add('192.168.0.4', r'192.168.0.1')
    else:
        assert False, 'Topo does not exist right now mate'

    iperf_start_clients(host_out_dir, cm, tcp)

################################################################################
# exps

@fab.task
@fab.runs_once
def exp_betak(tname):
    assert tname == 'star' or tname == '3hop' or tname == 'bae'

    @fab.task
    @fab.parallel
    def betak(out_dir, tname, beta, k):
        host_out_dir = makeout(out_dir, '{:03}-{:04}'.format(int(beta*100), k))
        run_react(host_out_dir, 'new', beta, k)
        topo(tname, host_out_dir, False)

    betas = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    for beta in betas:
        for k in range(250, 3250, 250):
            fab.execute(betak, '~/data/97_betak/{}'.format(tname), tname,
                    beta, k)
            time.sleep(15)
            fab.execute(stop_exp)

@fab.task
@fab.runs_once
def exp_comp(tname):

    @fab.task
    @fab.parallel
    def comp(out_dir, tname, use):
        host_out_dir = makeout(out_dir, use)
        if use != 'oldest':
            run_react(host_out_dir, use)
        else:
            run_react2(host_out_dir)
        topo(tname, host_out_dir, False)

    for use in  ['dot', 'new', 'old', 'oldest']:
        fab.execute(comp, "~/data/96_comp/{}".format(tname), tname, use)
        time.sleep(120)
        fab.execute(stop_exp)

@fab.task
@fab.runs_once
def exp_multi():
    ip2mac = {}
    fab.execute(collect_ip2mac_map, ip2mac)

    last = None
    for ip in ip2mac:
        if last is None or ip > last:
            last = ip
    last = long2dot(last)

    def multi_makeout(use, tcp):
        return makeout('~/data/95_multi/', '{}-{}-{}'.format(len(ip2mac), use,
                'tcp' if tcp else 'udp'))

    @fab.task
    @fab.parallel
    def multi(use, tcp):
        host_out_dir = multi_makeout(use, tcp)

        if use == 'new':
            status = json.loads(fab.run(
                    '{}/reservation/reserver.py get_status {}'.format(
                    project_path, get_my_ip())))
            capacity = float(status['capacity'])/100.0
            allocation = float(status['allocation'])/100.0
            run_react(host_out_dir, use, capacity=capacity, prealloc=allocation)
        else:
            run_react(host_out_dir, use)

        cm = ConnMatrix()
        cm.add('192.168.0.1', last)
        cm.add(last, r'NONE')
        roadtrip_start_clients(host_out_dir, cm, tcp)

    for use in  ['dot', 'new']:
        for tcp in [True, False]:
            for i in xrange(10):
                if use == 'new':
                    fab.execute(res_server_kickoff, ip2mac)
                    time.sleep(1) # wait for server to start

                    resp = fab.run(
                            '{}/reservation/reserver.py place_reservation' \
                            ' 192.168.0.1 {} 26'.format(project_path, last))
                    assert json.loads(resp)['placed']

                fab.execute(multi, use, tcp)
                time.sleep(120)
                fab.execute(stop_exp)

@fab.task
@fab.parallel
def exp_4con(use):
    assert(use == "dot" or use == "new" or use == "old" or use == 'oldest')

    host_out_dir = makeout('/groups/wall2-ilabt-iminds-be/react/old_react/data/01_4con', use)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')
    iperf_start_clients(host_out_dir, cm, tcp=True)

    if use != 'oldest':
        run_react(host_out_dir, use)
    else:
        run_react2(host_out_dir)

@fab.task
@fab.parallel
def exp_line(use):
    assert(use == "dot" or use == "new" or use == "old")

    host_out_dir = makeout('~/data/10_line', use)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.4')
    iperf_start_clients(host_out_dir, cm)

    run_react(host_out_dir, use)

@fab.task
@fab.parallel
def exp_longline(dot, udp=True, flows=1):
    #NAME = '{}lowflow'.format(flows)
    NAME = 'manyflow'.format(flows)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2$')
    cm.add('192.168.0.2', r'192.168.0.1$')
    cm.add('192.168.0.3', r'192.168.0.4$')
    cm.add('192.168.0.4', r'192.168.0.3$')
    cm.add('192.168.0.5', r'192.168.0.6$')
    cm.add('192.168.0.6', r'192.168.0.5$')
    cm.add('192.168.0.7', r'192.168.0.8$')
    cm.add('192.168.0.8', r'192.168.0.7$')
    cm.add('192.168.0.9', r'192.168.0.10$')
    cm.add('192.168.0.10', r'192.168.0.9$')

    trial = '{}_{}_{}'.format(NAME, 'udp' if udp else 'tcp',
            'dot' if dot else 'new')
    host_out_dir = makeout('~/data/11_longline', trial)

    iperf_start_clients(host_out_dir, cm, tcp=not(udp))
    #iperf_start_clients(host_out_dir, cm, rate='1M')
    run_react(host_out_dir, 'dot' if dot else 'new')

@fab.task
@fab.runs_once
def runner():
    for dot in [True, False]:
        for udp in [True, False]:
        #for flows in [1, 2]:
            fab.execute(exp_longline, dot, udp=udp)
            time.sleep(240)
            fab.execute(stop_exp)

@fab.task
@fab.parallel
def exp_concept(enable_react):
    enable_react = bool(strtobool(enable_react))

    subdir = 'react_on' if enable_react else 'react_off'
    host_out_dir = makeout('~/data/01_concept', subdir)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')
    iperf_start_clients(host_out_dir, cm)

    run_react(host_out_dir, 'new' if enable_react else None)

@fab.task
@fab.parallel
def exp_graph2():
    host_out_dir = makeout('~/data/98_graph2')

    nodes = range(len(fab.env.hosts))
    random.shuffle(nodes)

    cmd = 'ping -c 100 -I wls33 192.168.0.{0} > {1}/192.168.0.{0}'
    for n in nodes:
        with fab.settings(warn_only=True):
            fab.run(cmd.format(n + 1, host_out_dir))

@fab.task
@fab.parallel
def exp_cr_tuning(trial):
    assert trial in ('dot', 'new', 'cr')
    host_out_dir = makeout('~/data/42_cr_tuning', trial)

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')
    iperf_start_clients(host_out_dir, cm)

    if trial in ('dot', 'new'):
        run_react(host_out_dir, tuner=trial)
    else:
        run_cr_tuning(host_out_dir)

@fab.task
@fab.parallel
def exp_test(enable_react=False):
    if isinstance(enable_react, basestring):
        enable_react = bool(strtobool(enable_react))

    host_out_dir = makeout()

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.1')
    #cm.add('192.168.0.3', r'192.168.0.4')
    #cm.add('192.168.0.4', r'192.168.0.1')
    iperf_start_clients(host_out_dir, cm)

    if enable_react:
        run_react(host_out_dir)
