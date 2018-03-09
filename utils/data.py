#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
import networkx as nx

import sys
import os
import argparse
from glob import glob
import re
import itertools
from distutils.util import strtobool

# UDP server report
# timestamp      server      port client      port  ? interval   sent     band   jitter drop total %      out-of-order
# 20180307070534,192.168.0.2,5001,192.168.0.1,36966,3,0.0-2274.2,42819630,150625,38.257,4987,34116,14.618,28

def load_react_csv_data(node_dir, x_index, y_index):
    x_list = []
    y_list = []
    node_list = []

    node_dirs = glob('{}/*'.format(node_dir))
    paths = glob('{}/*/react.csv'.format(node_dir))

    assert len(node_dirs) == len(paths) and len(paths) != 0, \
            "Is there a missing react.csv file?"

    for i in xrange(len(paths)):
        path = paths[i]
        x_list.append(np.loadtxt(path, delimiter=',', usecols=(x_index,)))
        y_list.append(np.loadtxt(path, delimiter=',', usecols=(y_index,)))
        node_list.append(path.split('/')[-2])

    return x_list, y_list, node_list

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
    x_list, y_list, node_list = load_react_csv_data(node_dir, 0, y_index)

    first, last = get_xlim(x_list)
    for x in x_list:
        for i in xrange(len(x)):
            x[i] = x[i] - first
    plt.xlim([0, last - first])

    for i in xrange(len(x_list)):
        plt.plot(x_list[i], y_list[i], label=node_list[i])

def plot_react(node_dir, col='airtime', ylim=None):
    # Example react.csv row
    # 1520532965.14935,0.16000,0.20536,352,356

    if col == 'alloc':
        col, name, unit = (1, 'Airtime Allocation', '%')
    elif col == 'airtime':
        col, name, unit = (2, 'Airtime', '%')
    elif col == 'prev':
        col, name, unit = (3, 'Previous CW Size', '')
    elif col == 'next':
        col, name, unit = (4, 'Next CW Size', '')
    else:
        assert False, 'Not a valid react.csv column'

    if ylim is not None:
        ylim = float(ylim)

    plot_react_csv_data(node_dir, col)

    if ylim is not None:
        plt.ylim([0, ylim])

    plt.xlabel('Time')
    plt.ylabel('{} ({})'.format(name, unit))
    plt.title('{} vs. Time'.format(name))
    plt.legend()
    plt.show()

def converge_time(node_dir, cv_threshold):
    x_list, y_list, _ = load_react_csv_data(node_dir, 0, 2)
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

def convergence(node_dir, threshold=0.1):
    threshold = float(threshold)
    print converge_time(node_dir, threshold)

def heatmap(out_dir, threshold=0.1):
    threshold = float(threshold)

    beta_list = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    k_list = range(250, 3250, 250)

    low = (None, None, None)
    a = []
    for i in xrange(len(beta_list)):
        beta = beta_list[i]

        row = []
        for k in k_list:
            node_dir = '{}/{:03}-{:04}'.format(out_dir, int(beta*100), k)
            ct = converge_time(node_dir, threshold)

            if low[0] is None or ct < low[0]:
                low = (ct, beta, k)

            row.append(ct)

        print row
        a.append(row)

    print low

    _, ax = plt.subplots()
    ax.set_xticks(range(len(k_list)))
    ax.set_yticks(range(len(beta_list)))
    ax.set_xticklabels(k_list)
    ax.set_yticklabels(beta_list)

    plt.xlabel('k')
    plt.ylabel('BETA')
    plt.title('Convergence Varying BETA/k\n(Darker is faster)')
    plt.imshow(a, cmap='hot', interpolation='nearest')
    plt.show()

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

def get_graphs(node_dir, plot=False):
    if isinstance(plot, basestring):
        plot = bool(strtobool(plot))

    # Create a dictionary that maps IP addresses to testbed node names
    ip_to_node = {}
    for path in glob('{}/zotac*/192.168.0.1'.format(node_dir)):
        node = path.split('/')[-2]

        for line in open(path):
            if re.search('PING', line):
                ip_to_node[line.split()[4]] = node
                break

    # Graph G100 has edges between all 100% transmission probability links
    G100 = nx.DiGraph()
    # Graph Gall has edges between all non-zero transmission probability links
    Gall = nx.DiGraph()

    # Add edges to graphs
    for path in glob('{}/zotac*/192.*'.format(node_dir)):
        to_node = from_node = packet_loss = None

        for line in open(path):
            parts = line.split()

            if re.search('PING', line):
                assert(to_node is None and from_node is None)
                to_node = ip_to_node[parts[1]]
                from_node = ip_to_node[parts[4]]

            if re.search('packet loss', line):
                for i in xrange(len(parts)):
                    if parts[i] == 'packet':
                        assert(packet_loss is None)
                        assert(parts[i + 1] == 'loss,')
                        packet_loss = float(parts[i - 1].strip('%'))/100.0

        assert(to_node is not None and from_node is not None and
                packet_loss is not None)
        assert(not(packet_loss < 0.0) and not(packet_loss > 1.0))
        transmission_prob = 1 - packet_loss
        if transmission_prob == 1.0:
            G100.add_edge(from_node, to_node)
        if transmission_prob > 0.0:
            Gall.add_edge(from_node, to_node)

    # Sanity check, all edges in G100 should be in Gall
    for n1, n2 in G100.edges():
        assert(Gall.has_edge(n1, n2))

    if plot:
        for g in [G100, Gall]:
            nx.draw_networkx(g)
            plt.show()

    return G100, Gall

def find_paths(node_dir, length=1):
    length = int(length)

    G100, Gall = get_graphs(node_dir)
    paths = []

    # For each pair of nodes, check if the length of the shortest paths between
    # these nodes in G100 is if of the target length. If it is, check that there
    # is not a shorter path between the nodes in Gall. If there is not a shorter
    # path then the shortest paths in G100 are "high-quality" paths. This is
    # because each link in the path has a 100% transmission probability and
    # there are no lower probability links that would form a shorter path
    # between the pair of nodes.
    for n1 in G100:
        for n2 in G100:
            try:
                if nx.shortest_path_length(G100, n1, n2) == \
                        nx.shortest_path_length(Gall, n1, n2) and \
                        nx.shortest_path_length(G100, n1, n2) == length:
                    for path in nx.all_shortest_paths(G100, n1, n2):
                        paths.append(path)
            except nx.NetworkXNoPath:
                pass

    # Filter out uni-directional paths and print bi-directional paths
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

def find_star(node_dir, plot=False):
    if isinstance(plot, basestring):
        plot = bool(strtobool(plot))

    G100, Gall = get_graphs(node_dir)

    def has_edge(G, n1, n2):
        return G.has_edge(n1, n2) and G.has_edge(n2, n1)

    for nodes in itertools.permutations(G100, 5):
        star = True

        # Check that each outside node only has an edge to the center node
        for i in range(4):
            if not(has_edge(G100, nodes[i], nodes[4])) or \
                    has_edge(Gall, nodes[i], nodes[(i + 1) % 4]) or \
                    has_edge(Gall, nodes[i], nodes[(i + 2) % 4]) or \
                    has_edge(Gall, nodes[i], nodes[(i + 3) % 4]):
                star = False
                break

        if star:
            if plot:
                nx.draw_networkx(G100.subgraph(nodes))
                plt.show()
            print nodes

def plot_network(node_dir):
    G100, _ = get_graphs(node_dir)

    nx.draw_networkx(G100)
    plt.show()


if __name__ == '__main__':
    fn_map = {
        'plot_react': plot_react,
        'convergence': convergence,
        'throughput': thr,
        'get_graphs': get_graphs,
        'find_paths': find_paths,
        'find_star': find_star,
        'plot_network': plot_network,
        'heatmap': heatmap
    }

    p = argparse.ArgumentParser()
    p.add_argument('dir', help='data directory for specific trial')
    p.add_argument('command', choices=fn_map,
            help='data processing sub-command')
    p.add_argument('override', nargs='*',
            help='override functions default arguments')
    args = p.parse_args()

    assert os.path.isdir(args.dir), "Bad dir argument?"

    override = dict(zip(args.override[::2], args.override[1::2]))
    fn_map[args.command](args.dir, **override)
