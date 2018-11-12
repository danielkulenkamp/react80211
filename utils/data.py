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

def plot_react(node_dir, col='airtime', ylim=1.0, save=None, title=None):
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

    if isinstance(ylim, basestring):
        ylim = float(ylim)

    plot_react_csv_data(node_dir, col)

    if ylim is not None:
        plt.ylim([0, ylim])

    if title is None:
        title = ''
    else:
        title += ': '
    title += '{} vs. Time'.format(name)

    plt.xlabel('Time')
    plt.ylabel('{} ({})'.format(name, unit))
    plt.title(title)
    plt.legend()

    if save is None:
        plt.show()
    else:
        plt.savefig(save)

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
    print out_dir
    threshold = float(threshold)

    beta_list = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
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

def thr(path):
    throughput = None

    for line in open(path):
        parts = line.split(',')
        start, end = map(float, parts[6].split('-'))

        if start == 0.0 and end > 1.0:
            assert throughput is None, 'Already parsed throughput'
            throughput = float(parts[7])*8.0/end
            break

    assert throughput is not None, 'Did not parse throughput'
    return throughput

def plot_thr(trial_dir, proto='tcp', plot=True):
    def get_path(trial_dir, alg, proto):
        expand = '{}/{}-{}/zotac*/192.*.csv'.format(trial_dir, alg, proto)
        paths = glob(expand)
        assert len(paths) > 0, 'No path: ' + expand
        assert len(paths) == 1, 'More than one path: ' + expand
        return paths[0]

    dot_path = get_path(trial_dir, 'dot', proto)
    new_path = get_path(trial_dir, 'new', proto)

    throughput = []
    for path in [dot_path, new_path]:
        throughput.append(thr(path))

    # Convert to mbps
    throughput = map(lambda bps: bps/1000.0/1000.0, throughput)
    print throughput

    objects = ('802.11', 'New Tuning')
    y_pos = np.arange(len(objects))

    plt.bar(y_pos, throughput, align='center', alpha=0.5)
    plt.xticks(y_pos, objects)
    plt.ylabel('Throughput (mbps)')
    plt.title('Throughput: 802.11 vs New Tuning')

    plt.show()

def get_graphs(node_dir):
    # Create a dictionary that maps IP addresses to testbed node names
    ip_to_node = {}
    for path in glob('{}/*/192.168.0.1'.format(node_dir)):
        node = path.split('/')[-2]

        found = False
        for line in open(path):
            if re.search('PING', line):
                found = True
                ip_to_node[line.split()[4]] = node
                break
        assert found, "Can't find IP address for node {}".format(node)
    assert len(ip_to_node) != 0, "Didn't find any nodes"

    # Graph G100 has edges between all 100% transmission probability links
    G100 = nx.DiGraph()
    # Graph Gall has edges between all non-zero transmission probability links
    Gall = nx.DiGraph()

    # Add edges to graphs
    for path in glob('{}/*/192.*'.format(node_dir)):
        to_node = from_node = packet_loss = None

        for line in open(path):
            parts = line.split()

            if re.search('PING', line):
                assert to_node is None and from_node is None, \
                        'More than one line with "PING" in it?'
                to_node = ip_to_node[parts[1]]
                from_node = ip_to_node[parts[4]]

            if re.search('packet loss', line):
                for i in xrange(len(parts)):
                    if parts[i] == 'packet':
                        assert packet_loss is None, \
                                'More than one line with "packet loss" in it?'
                        assert parts[i + 1] == 'loss,', \
                                'Packet loss not where expected in line'
                        packet_loss = float(parts[i - 1].strip('%'))/100.0

        assert to_node is not None and from_node is not None, \
                "Didn't find both to and from nodes"
        assert packet_loss is not None, "Didn't find packet loss"
        assert not(packet_loss < 0.0) and not(packet_loss > 1.0), \
                'Packet loss out of range: {}'.format(packet_loss)
        transmission_prob = 1 - packet_loss
        if transmission_prob == 1.0:
            G100.add_edge(from_node, to_node)
        if transmission_prob > 0.0:
            Gall.add_edge(from_node, to_node)

    for n1, n2 in G100.edges():
        assert Gall.has_edge(n1, n2), \
                'Sanity check failed, all edges in G100 should be in Gall'

    return G100, Gall

def net_graph(node_dir):
    G100, Gall = get_graphs(node_dir)

    for g in [G100, Gall]:
        nx.draw_networkx(g)
        plt.show()

def find_paths(node_dir, length=4):
    length = int(length)

    G100, Gall = get_graphs(node_dir)

    def valid(p):
        try:
            for G in (G100, Gall):
                for n1, n2 in ((p[0], p[-1]), (p[-1], p[0])):
                    g = G.subgraph(p)
                    if nx.shortest_path_length(g, n1, n2) != len(p) - 1:
                        return False
        except nx.NetworkXNoPath:
            return False
        return True

    def check(p):
        if len(p) - 1 == length:
            print p
            return

        for n in G100:
            q = p + (n,)
            if valid(q):
                check(q)

    for n in G100:
        check((n,))

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

# UDP server report indexes:
# --------------------------
# 00 timestap 20180307070534
# 01 server 192.168.0.2
# 02 port 5001
# 03 client 192.168.0.1
# 04 client port 36966
# 05 ? 3
# 06 interval 0.0-2274.2
# 07 bytes sent 42819630
# 08 bit/s 150625
# 09 jitter 38.257
# 10 dropped 4987
# 11 total 34116
# 12 % dropped 14.618
# 13 out of order 28
def get_server_report(node_dir, nodes, index):
    data = []

    # We requrie nodes list to order data
    for node in nodes:
        paths = glob('{}/{}/192.*.csv'.format(node_dir, node))
        assert len(paths) == 1, ' '.join(paths)
        path = paths[0]

        for line in open(path):
            parts = line.split(',')

            if len(parts) == 14:
                data.append(float(parts[index]))
                break

    return data

def comp_barchart(data, nodes, ylabel, yunits):
    fig, ax = plt.subplots()
    index = np.arange(len(nodes))
    bar_width = 0.25
    opacity = 0.8

    rects1 = plt.bar(index, data[0], bar_width,
                     alpha=opacity,
                     color='b',
                     label='802.11')

    rects2 = plt.bar(index + bar_width, data[1], bar_width,
                     alpha=opacity,
                     color='g',
                     label='Old Tuning')

    rects2 = plt.bar(index + 2*bar_width, data[2], bar_width,
                     alpha=opacity,
                     color='r',
                     label='New Tuning')

    plt.xlabel('Node')
    plt.ylabel('{} ({})'.format(ylabel, yunits))
    plt.title(ylabel + ' by Node')
    plt.xticks(index + bar_width, nodes)
    plt.legend()

    plt.tight_layout()
    plt.show()

def comp_setup():
    ### star
    nodes = ['zotacB2', 'zotacF1', 'zotacF4', 'zotacI4']
    dot_dir = '/home/mattm/ms/data/96_comp/star/003/dot'
    old_dir = '/home/mattm/ms/data/96_comp/star/003/old'
    new_dir = '/home/mattm/ms/data/96_comp/star/003/new'
    ### 3hop
    #nodes = ['zotacB2', 'zotacF3', 'zotacI4', 'zotacM20']
    #dot_dir = '/home/mattm/ms/data/96_comp/3hop/007/dot'
    #old_dir = '/home/mattm/ms/data/96_comp/3hop/007/old'
    #new_dir = '/home/mattm/ms/data/96_comp/3hop/007/new'
    ### bae
    #nodes = ['zotacK1', 'zotacK2', 'zotacK3', 'zotacK4']
    #dot_dir = '/home/mattm/ms/data/96_comp/bae/001/dot'
    #old_dir = '/home/mattm/ms/data/96_comp/bae/001/old'
    #new_dir = '/home/mattm/ms/data/96_comp/bae/001/new'

    return nodes, dot_dir, old_dir, new_dir

def comp_thr(unused):
    nodes, dot_dir, old_dir, new_dir = comp_setup()

    def kbps(x):
        return x/1000.0

    dot_thr = map(kbps, get_server_report(dot_dir, nodes, 8))
    old_thr = map(kbps, get_server_report(old_dir, nodes, 8))
    new_thr = map(kbps, get_server_report(new_dir, nodes, 8))

    print dot_thr
    print old_thr
    print new_thr

    comp_barchart([dot_thr, old_thr, new_thr], nodes, 'Throughput', 'kbps')

def comp_aggthr(unused):
    nodes, dot_dir, old_dir, new_dir = comp_setup()

    def kb(x):
        return x/(1024.0 * 1024.0)

    dot_thr = map(kb, get_server_report(dot_dir, nodes, 7))
    old_thr = map(kb, get_server_report(old_dir, nodes, 7))
    new_thr = map(kb, get_server_report(new_dir, nodes, 7))

    print dot_thr
    print old_thr
    print new_thr

    agg = [sum(dot_thr), sum(old_thr), sum(new_thr)]
    print agg

    objects = ('802.11', 'Old Tuning', 'New Tuning')
    y_pos = np.arange(len(objects))

    plt.bar(y_pos, agg, align='center', alpha=0.5)
    plt.xticks(y_pos, objects)
    plt.ylabel('Aggregate Throughput (MiB)')
    plt.title('Aggregate Throughput by MAC Implementation')

    plt.show()

def comp_jitter(unused):
    nodes, dot_dir, old_dir, new_dir = comp_setup()

    dot_thr = get_server_report(dot_dir, nodes, 9)
    old_thr = get_server_report(old_dir, nodes, 9)
    new_thr = get_server_report(new_dir, nodes, 9)

    print dot_thr
    print old_thr
    print new_thr

    comp_barchart([dot_thr, old_thr, new_thr], nodes, 'Jitter', 'ms')

def comp_drop(unused):
    nodes, dot_dir, old_dir, new_dir = comp_setup()

    dot_thr = get_server_report(dot_dir, nodes, 12)
    old_thr = get_server_report(old_dir, nodes, 12)
    new_thr = get_server_report(new_dir, nodes, 12)

    print dot_thr
    print old_thr
    print new_thr

    comp_barchart([dot_thr, new_thr, old_thr], nodes, 'Drop Rate', '%')

if __name__ == '__main__':
    fn_map = {
        'plot_react': plot_react,
        'convergence': convergence,
        'plot_thr': plot_thr,
        'net_graph': net_graph,
        'find_paths': find_paths,
        'find_star': find_star,
        'plot_network': plot_network,
        'heatmap': heatmap,
        'comp_thr': comp_thr,
        'comp_aggthr': comp_aggthr,
        'comp_jitter': comp_jitter,
        'comp_drop': comp_drop
    }

    dirs = []
    fn_name = ""
    override = {}

    # Custom argument parsing
    try:
        assert len(sys.argv) >= 3, 'Not enough arguments'

        dirs = []
        for i in xrange(1, len(sys.argv)):
            arg = sys.argv[i]

            if arg == '--':
                break

            assert os.path.isdir(arg), '{} is not a directory'.format(arg)
            dirs.append(arg)

        assert len(dirs) > 0, 'No DIR argument specified'

        fn_name = sys.argv[i + 1]
        assert fn_name in fn_map, 'Bad function name: {}'.format(fn_name)

        for j in xrange(i + 2, len(sys.argv)):
            arg = sys.argv[j]
            parts = arg.split('=')

            assert len(parts) == 1 or len(parts) == 2, \
                    'Bad override: {}'.format(arg)
            key = parts[0]
            if len(parts) == 1:
                value = True
            else:
                value = parts[1]

            override[key] = value
    except AssertionError as e:
        print 'Error: ' + e.message
        print 'Usage: data.py DIR [DIR...] -- FUNCTION [override[=value]' \
                ' [override[=value]...]]'
        print
        print 'Functions:'
        print '    ' + '\n    '.join(fn_map.keys())
        exit()

    for d in dirs:
        print d
        fn_map[fn_name](d, **override)
