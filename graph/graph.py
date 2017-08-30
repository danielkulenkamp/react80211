#!/usr/bin/python -i

import networkx as nx
import matplotlib.pyplot as plt

def parse_graphf(graphf='graph', pkts_sent=1000.0):
    G = nx.DiGraph()

    for line in open(graphf):
        parts = line.split(',')

        node = parts[0]
        for i in range(1, len(parts)):
            node2, pkts_recvd = parts[i].split(':')

            weight = float(pkts_recvd)/pkts_sent
            if node != node2 and weight > 0.0:
                G.add_edge(node, node2, weight=weight)

    return G

def draw_graph(G):
    nx.draw(G, label_color='g', edge_color='b', with_labels=True)
    plt.show()

G = parse_graphf()
