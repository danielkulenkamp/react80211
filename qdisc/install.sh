#!/bin/bash
# assumes kernel module has already been built

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root"
    exit
fi

apt-get install linux-headers-$(uname -r)
make install
depmod
modprobe sch_react
