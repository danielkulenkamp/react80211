#!/bin/bash

sudo apt-get install -y linux-headers-$(uname -r)

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root"
    exit
fi

# assumes kernel module has already been built after this point

# uninstall
tc qdisc del dev wlan0 root
modprobe -r sch_react

# install
make install
depmod
modprobe sch_react
tc qdisc add dev wlan0 root react
