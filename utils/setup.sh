#!/bin/bash

sudo rm /etc/apt/apt.conf.d/01proxy
sudo apt-get install -y fabric && fab setup
