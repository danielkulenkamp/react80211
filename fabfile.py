#! /usr/bin/env python2
'''Utilities for performing REACT80211 experimets.
Requires Python 2.X for Fabric.
Author: Fabrizio Giuliano
'''

###
# my includes
from helpers.conn_matrix import ConnMatrix

from distutils.util import strtobool
import time
###

import os
import os.path
import datetime
import re
import sys
#import scapy.all as scapy



from StringIO import StringIO
from fabric.api import get


import fabric
import fabric.api as fab
from fabric.api import hide, run, get
import fabric.utils
import json
hosts_driver=[];
hosts_txpower=[]
neigh_list=[]
#verbosity
#fabric.state.output['running'] = False
#fab.output_prefix = False
project_path=path=os.getcwd()
data_path="{}/{}".format(project_path,"data")

@fab.task
@fab.parallel
def install_python_deps():
    fab.sudo("apt-get install -y python-scapy python-netifaces python-numpy")

@fab.task
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
hosts_driver=set_hosts('node_info.txt')

@fab.task
@fab.parallel
# Ad-hoc node association
#echo "usage $0 <iface> <essid> <freq> <power> <rate> <ip> <mac> <reload[1|0]>"
def associate(driver,iface,essid,freq,txpower,rate,ip_addr,mac_address="aa:bb:cc:dd:ee:ff",skip_reload=False,rts='off'):
    with fab.settings(warn_only=True):
        if driver=="ath9k":
            if skip_reload == False:
                fab.run('sudo rmmod ath9k ath9k_common ath9k_hw ath mac80211 cfg80211')
                #fab.run('sudo modprobe ath9k')
                fab.sudo('cd {0}/backports-wireless/; bash ./build.sh --load-module; cd {0} '.format(project_path))
            else:
                fab.run('iw {0} ibss leave'.format(iface))
            fab.run('sudo iwconfig {0} mode ad-hoc; sudo ifconfig {0} {5} up;sudo iwconfig {0} txpower {3}dbm; sudo iwconfig {0} rate {4}M fixed;sudo iw dev {0} ibss join {1} {2} fixed-freq {6}'.format(iface,essid,freq,txpower,rate,ip_addr,mac_address))
            iface_mon='mon0';
            fab.sudo('iw dev {0} interface add {1} type monitor'.format(iface,iface_mon));
            fab.sudo('ifconfig {0} up'.format(iface_mon));
            fab.run('sudo iwconfig {0} rts {1}'.format(iface,rts))

        elif driver=="b43":

            if skip_reload == False:
                fab.run('sudo rmmod b43')
                fab.run('sudo modprobe b43 qos=0')
            else:
                fab.run('iw {0} ibss leave'.format(iface))
            fab.run('sudo iwconfig {0} mode ad-hoc; sudo ifconfig {0} {5} up;sudo iwconfig {0} txpower {3}; sudo iwconfig {0} rate {4}M fixed;sudo iw dev {0} ibss join {1} {2} fixed-freq {6}'.format(iface,essid,freq,txpower,rate,ip_addr,mac_address))
        else:
            "driver {} not supported".format(driver)
            return

@fab.task
@fab.parallel
def set_txpower(txpower):
    fab.run('sudo iwconfig wlan0 txpower {0}'.format(txpower))

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
    fab.execute(associate,driver,'wlan0','test',freq,txpower,6,'192.168.0.{0}'.format(i_ip+1),'aa:bb:cc:dd:ee:ff',skip_reload=False,rts='250',hosts=[fab.env.hosts[i_ip]])

@fab.task
@fab.parallel
def stop_react():
    with fab.settings(warn_only=True):
        fab.sudo("pid=$(pgrep _react.py) && kill -9 $pid")

@fab.task
@fab.parallel
def run_react(out_dir=None, beta=None, k=None, no_react=False, ct=None,
        sleep_time=None):
    args = []

    if out_dir is None:
        out_dir = makeout()
    args.append('{}/react.csv'.format(out_dir))

    if beta is not None:
        args.append('-b')
        args.append(str(beta))

    if k is not None:
        args.append('-k')
        args.append(str(k))

    if no_react:
        args.append('-n')

    if ct is not None:
        args.append('-c')
        args.append(str(ct))

    if sleep_time is not None:
        args.append('-t')
        args.append(str(sleep_time))

    stop_react();
    fab.sudo('setsid {}/_react.py {} &>/dev/null </dev/null &'.format(
        project_path, ' '.join(args)), pty=False)

################################################################################
# time

@fab.task
@fab.parallel
def time_sync():
    fab.sudo('service ntp stop')
    fab.sudo('ntpdate time.nist.gov')

################################################################################
# screen

def screen_start_session(name, cmd):
    fab.run('screen -S {} -dm bash -c "{}"'.format(name, cmd), pty=False)

def screen_stop_session(name):
    with fab.settings(warn_only=True):
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
# iperf

def get_my_ip(dev='wlan0'):
    cmd = 'python -c \'from netifaces import *; print ifaddresses("{}")[AF_INET][0]["addr"]\''
    return fab.run(cmd.format(dev))

@fab.task
def iperf_start_servers():
    screen_start_session('iperf_server', 'iperf -s -u')

@fab.task
def iperf_start_clients(host_out_dir, conn_matrix, rate='1G'):
    for server in conn_matrix.links(get_my_ip()):
        screen_start_session('iperf_client',
                'iperf -c {0} -u -b {2} -t -1 -i 3 -yC | tee {1}/{0}.csv'
                .format(server, host_out_dir, rate))

@fab.task
def iperf_stop_clients():
    screen_stop_session('iperf_client')

################################################################################
# exps

def makeout(out_dir='~/data/test', trial_dir=None):
    subdirs = []

    subdirs.append(out_dir)

    today = datetime.datetime.today()
    subdirs.append('{:02}{:02}'.format(today.month, today.day))

    if trial_dir is not None:
        subdirs.append(trial_dir)

    subdirs.append(fab.env.host)

    host_out_dir = '/'.join(subdirs)
    fab.run('mkdir -p {}'.format(host_out_dir))
    return host_out_dir

@fab.task
@fab.parallel
def setup():
    time_sync()
    install_python_deps()
    network(freq=5180)
    iperf_start_servers()

@fab.task
@fab.parallel
def exp_test():
    host_out_dir = makeout()

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')
    iperf_start_clients(host_out_dir, cm)

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

    run_react(out_dir=host_out_dir, no_react=not(enable_react))

@fab.task
@fab.parallel
def exp_hilo(trial):
    if trial == 'none':
        no_react = True
        ct = None
    elif trial == 'low':
        no_react = False
        ct = 0
    elif trial == 'high':
        no_react = False
        ct = 1023
    else:
        exit(1)

    host_out_dir = makeout('~/data/02_hilo/{}'.format(trial))

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')
    iperf_start_clients(host_out_dir, cm)

    run_react(out_dir=host_out_dir, no_react=no_react, ct=ct)

@fab.task
@fab.parallel
def exp_parameters(beta, k):
    host_out_dir = makeout('~/data/03_parameters', 'b{:03}_k{:03}'.format(
        int(float(beta)*100.0), int(k)))

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')
    iperf_start_clients(host_out_dir, cm)

    run_react(out_dir=host_out_dir, beta=beta, k=k)

@fab.task
def exp_cnert_sat(out_dir):
    host_out_dir = "{}/{}".format(out_dir, fab.env.host)
    fab.run('mkdir -p {}'.format(host_out_dir))

    run_react(bw_req=6000, enable_react='YES')

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.5')
    cm.add('192.168.0.5', r'192.168.0.6')
    cm.add('192.168.0.6', r'192.168.0.7')
    cm.add('192.168.0.7', r'192.168.0.1')

    iperf_start_clients(host_out_dir, cm)

@fab.task
def exp_cnert_noise(out_dir, rate):
    host_out_dir = "{}/{}".format(out_dir, fab.env.host)
    fab.run('mkdir -p {}'.format(host_out_dir))

    if re.match(r'192\.168\.0\.(1|4)', get_my_ip()):
        cm = ConnMatrix()
        cm.add('192.168.0.1', r'192.168.0.4')
        cm.add('192.168.0.4', r'192.168.0.1')

        run_react(bw_req=6000, enable_react='YES')
        iperf_start_clients(host_out_dir, cm)
    elif int(rate) > 0:
        cm = ConnMatrix()
        cm.add('192.168.0.2', r'192.168.0.3')
        cm.add('192.168.0.3', r'192.168.0.2')

        iperf_start_clients(host_out_dir, cm, rate)

@fab.task
@fab.parallel
def stop_exp():
    stop_react()
    iperf_stop_clients()

