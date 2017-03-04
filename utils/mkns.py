#!/usr/bin/python

from __future__ import print_function
import sys

header = """set ns [new Simulator]
source tb_compat.tcl"""

node = """
set node%02d [$ns node]
tb-fix-node node%02d %s
tb-set-node-os node%02d UBUNTU12-linux-3.8"""

footer = """
$ns run"""

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: mkns.py node_1 [node_2 ... node_n]", file=sys.stderr)
        quit()

    print(header)

    for i in xrange(1, len(sys.argv)):
        name = sys.argv[i]
        print(node % (i, i, name, i))

    print(footer)
