#!/usr/bin/python

import networkx as nx
import matplotlib.pyplot as plt

G = nx.Graph()

for line in open('graph'):
    parts = line.split(',')

    node = parts[0]
    for i in range(1, len(parts)):
        node2, weight = parts[i].split(':')
        weight = int(weight)

        if node != node2 and weight > 900:
            G.add_edge(node, node2)

print nx.diameter(G)

nx.draw(G, label_color='g', edge_color='b', with_labels=True)
plt.savefig('90.png')
plt.show()
