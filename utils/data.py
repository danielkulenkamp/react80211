#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
import networkx as nx

import sys
import os
import argparse
from glob import glob
import re

def load_react_csv_data(node_dir, x_index, y_index):
    x_list = []
    y_list = []

    nodes = glob('{}/*'.format(node_dir))
    paths = glob('{}/*/react.csv'.format(node_dir))

    assert(len(nodes) == len(paths) and len(paths) != 0) # missing react.csv?

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

def airtime(node_dir, col=2):
    plot_react_csv_data(node_dir, int(col))
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

def thr(node_dir):
    i = 1
    for path in glob('{}/zotac*/192.*.csv'.format(node_dir)):
        thr = np.loadtxt(path, delimiter=',', usecols=(8,))/1000000
        print "{:02}\t{:.5f}\t{:.5f}".format(i, np.mean(thr), np.std(thr))
        i += 1

    #all_bytes_sent = 0
    #for path in glob('{}/zotac*/192.*.csv'.format(node_dir)):
    #    thr = np.loadtxt(path, delimiter=',', usecols=(7,))
    #    all_bytes_sent += np.sum(thr[:240])
    #print all_bytes_sent

def graph(node_dir):
    # Create a dictionary that maps IP addresses to testbed node names
    ip_to_node = {}
    for path in glob('{}/zotac*/192.168.0.1'.format(node_dir)):
        node = path.split('/')[-2]

        for line in open(path):
            if re.search('PING', line):
                ip_to_node[line.split()[4]] = node
                break

    # Graph G has edges between all 100% transmission probability links
    G = nx.DiGraph()
    # Graph H has edges between all non-zero transmission probability links
    H = nx.DiGraph()

    # Add edges to graphs
    for path in glob('{}/zotac*/192.*'.format(node_dir)):
        to_node = from_node = sent = recvd = None

        for line in open(path):
            parts = line.split()

            if re.search('PING', line):
                assert(to_node is None and from_node is None)
                to_node = ip_to_node[parts[1]]
                from_node = ip_to_node[parts[4]]

            if re.search('transmitted', line):
                assert(sent is None and recvd is None)
                sent = parts[0]
                recvd = parts[3]

        assert(to_node is not None and from_node is not None)
        assert(sent is not None and recvd is not None)
        transmission_prob = float(recvd)/float(sent)

        if transmission_prob == 1.0:
            G.add_edge(from_node, to_node)
        if transmission_prob > 0.0:
            H.add_edge(from_node, to_node)

    # Find all paths of length equal to the diameter
    diameter = nx.diameter(G)
    paths = []
    for n1 in G:
        for n2 in G:
            # Check if (high-quality) diameter length path(s) exist in G without
            # there being a shorter (low-quality) path in H
            if nx.shortest_path_length(G, n1, n2) == \
                    nx.shortest_path_length(H, n1, n2) and \
                    nx.shortest_path_length(G, n1, n2) == diameter:
                for path in nx.all_shortest_paths(G, n1, n2):
                    paths.append(path)

    # Filter out uni-directional paths
    for i in range(len(paths)):
        if len(paths[i]) == 0:
            break

        for j in range(len(paths)):
            if i != j:
                paths[j].reverse()
                if paths[i] == paths[j]:
                    print paths[i]
                    paths[i] = []
                    paths[j] = []
                    break
                paths[j].reverse()

if __name__ == '__main__':
    fn_map = { 'airtime': airtime, 'ct': ct, 'convergence': convergence,
            'throughput': thr, 'graph': graph }

    p = argparse.ArgumentParser()
    p.add_argument('node_dir', help='data directory for specific trial')
    p.add_argument('command', choices=fn_map,
            help='data processing sub-command')
    p.add_argument('override', nargs='*',
            help='override functions default arguments')
    args = p.parse_args()

    assert(os.path.isdir(args.node_dir)) # bad node_dir argument?

    fn_map[args.command](args.node_dir, *args.override)
