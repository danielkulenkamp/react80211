#!/usr/bin/python

import matplotlib.pyplot as plt
import numpy as np

import sys
import argparse
from glob import glob

def set_xlim(x_list):
    first = x_list[0][0]
    last = x_list[0][-1]

    for x in x_list:
        if x[0] > first:
            first = x[0]

        if x[-1] < last:
            last = x[-1]

    for x in x_list:
        for i in xrange(len(x)):
            x[i] = x[i] - first

    plt.xlim([0, last - first])

def load_react_csv_data(node_dir, x_index, y_index, x_list, y_list):
    paths = glob('{}/*/react.csv'.format(node_dir))
    for i in xrange(len(paths)):
        path = paths[i]
        x_list.append(np.loadtxt(path, delimiter=',', usecols=(x_index,)))
        y_list.append(np.loadtxt(path, delimiter=',', usecols=(y_index,)))

def plot_node_data(x_list, y_list):
    for i in xrange(len(x_list)):
        plt.plot(x_list[i], y_list[i], label='Node {}'.format(i))

def airtime(node_dir)
    x_list = []
    y_list = []

    load_react_csv_data(node_dir, 0, 2, x_list, y_list)
    set_xlim(x_list)
    plot_node_data(x_list, y_list)

    plt.xlabel('Time')
    plt.ylabel('Airtime (%)')
    plt.title('Airtime with REACT')
    plt.legend()
    plt.show()

def thr():
    i = 1
    for n in nodes:
        path = glob('{}/zotac{}/192.*.csv'.format(trial, n))[0]
        thr = np.loadtxt(path, delimiter=',', usecols=(8,))/1000000
        print "{} {} {}".format(i, np.mean(thr), np.std(thr))

        i += 1

if __name__ == '__main__':
    fn_map = { 'airtime': airtime }

    p = argparse.ArgumentParser()
    p.add_argument('command', choices=fn_map,
            help='data processing sub-command')
    p.add_argument('node_dir', action='store',
            help='data directory for specific trial')
    args = p.parse_args()

    fn_map[args.command](args.node_dir)

