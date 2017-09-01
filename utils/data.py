#!/usr/bin/python

import matplotlib.pyplot as plt
import numpy as np

import sys
import argparse
from glob import glob

def load_react_csv_data(node_dir, x_index, y_index):
    x_list = []
    y_list = []

    # TODO: check if this file exists
    paths = glob('{}/*/react.csv'.format(node_dir))
    for i in xrange(len(paths)):
        path = paths[i]
        x_list.append(np.loadtxt(path, delimiter=',', usecols=(x_index,)))
        y_list.append(np.loadtxt(path, delimiter=',', usecols=(y_index,)))

    return x_list, y_list

def get_xlim(x_list):
    first = x_list[0][0]
    last = x_list[0][-1]

    for x in x_list:
        if x[0] > first:
            first = x[0]

        if x[-1] < last:
            last = x[-1]

    return first, last

def plot_react_csv_data(node_dir, y_index):
    x_list, y_list = load_react_csv_data(node_dir, 0, y_index)

    first, last = get_xlim(x_list)
    for x in x_list:
        for i in xrange(len(x)):
            x[i] = x[i] - first
    plt.xlim([0, last - first])

    for i in xrange(len(x_list)):
        plt.plot(x_list[i], y_list[i], label='Node {}'.format(i))

def airtime(node_dir):
    plot_react_csv_data(node_dir, 2)
    plt.xlabel('Time')
    plt.ylabel('Airtime (%)')
    plt.title('Airtime vs. Time')
    plt.legend()
    plt.show()

def ct(node_dir):
    plot_react_csv_data(node_dir, 4)
    plt.xlabel('Time')
    plt.ylabel('CT')
    plt.title('Contention Time (CT) vs. Time')
    plt.legend()
    plt.show()

def converge_time(node_dir, cv_threshold=0.10):
    x_list, y_list = load_react_csv_data(node_dir, 0, 4)
    first, _ = get_xlim(x_list)

    # all y should start at same x and be same length
    for i in xrange(len(x_list)):
        x = x_list[i]

        first_i = 0
        while x[first_i] < first:
            first_i += 1
        y_list[i] = y_list[i][first_i:]

    min_len = min(map(len, y_list))
    for i in xrange(len(y_list)):
        y_list[i] = y_list[i][:min_len]

    data = np.column_stack(y_list)

    for i in xrange(len(data[...,0])):
        # coefficient of variation
        cv = data[i:].std(axis=0) / data[i:].mean(axis=0)

        if (cv < cv_threshold).all():
            return x_list[0][i] - first

    # does not converge
    return x_list[0][-1] - first

def convergence(node_dir):
    print converge_time(node_dir)

def thr():
    i = 1
    for n in nodes:
        path = glob('{}/zotac{}/192.*.csv'.format(trial, n))[0]
        thr = np.loadtxt(path, delimiter=',', usecols=(8,))/1000000
        print "{} {} {}".format(i, np.mean(thr), np.std(thr))

        i += 1

if __name__ == '__main__':
    fn_map = { 'airtime': airtime, 'ct': ct, 'convergence': convergence }

    p = argparse.ArgumentParser()
    p.add_argument('command', choices=fn_map,
            help='data processing sub-command')
    p.add_argument('node_dir', action='store',
            help='data directory for specific trial')
    args = p.parse_args()

    fn_map[args.command](args.node_dir)
