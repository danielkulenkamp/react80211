#! /usr/bin/env python2
'''Utilities for performing REACT80211 experimets.
Requires Python 2.X for Fabric.
Author: Fabrizio Giuliano
'''

from helpers.conn_matrix import ConnMatrix

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
    fab.sudo("apt-get install python-scapy python-netifaces")

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
        fab.sudo("pid=$(pgrep react.py) && kill -9 $pid")

@fab.task
@fab.parallel
def run_react(bw_req=6000,enable_react='NO',data_path=data_path):
    react_flag=''
    if enable_react=='YES':
        react_flag='-e'
    with fab.settings(warn_only=True):
        stop_react();
        fab.sudo('nohup {}/react.py -i wlan0 -t 0.1 -r {} {} -o {} > react.out 2> react.err < /dev/null &'.format(project_path,bw_req,react_flag,data_path), pty=False)

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
def iperf_start_clients(host_out_dir, conn_matrix, rate=6000):
    for server in conn_matrix.links(get_my_ip()):
        screen_start_session('iperf_client',
                'iperf -c {0} -u -b {2}K -t -1 -i 3 -yC | tee {1}/{0}.csv'
                .format(server, host_out_dir, rate))

@fab.task
def iperf_stop_clients():
        screen_stop_session('iperf_client')

@fab.task
def airtime_record(host_out_dir):
    screen_start_session('airtime',
            'python -u ~/react80211/utils/airtime.py 1 > {}/airtime.csv'
            .format(host_out_dir))

@fab.task
def airtime_stop():
    screen_stop_session('airtime')

################################################################################
# exps

@fab.task
def exp_start():
    install_python_deps()
    network(freq=5180)
    iperf_start_servers()

@fab.task
def exp_test(out_dir):
    host_out_dir = "{}/{}".format(out_dir, fab.env.host)
    fab.run('mkdir -p {}'.format(host_out_dir))

    run_react(bw_req=6000, enable_react='YES')

    cm = ConnMatrix()
    cm.add('192.168.0.1', r'192.168.0.2')
    cm.add('192.168.0.2', r'192.168.0.3')
    cm.add('192.168.0.3', r'192.168.0.4')
    cm.add('192.168.0.4', r'192.168.0.1')

    iperf_start_clients(host_out_dir, cm)
    airtime_record(host_out_dir)

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
def exp_stop():
    stop_react()
    iperf_stop_clients()
    #airtime_stop()

