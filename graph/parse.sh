#!/bin/bash

if [[ -z $1 ]]; then
    echo "Usage: parse.sh data/99_graph/DDMM"
    exit
fi

cd "$1"

for n1 in *; do
    echo -n $n1

    for n2 in *; do
        echo -n ",$n2:$(grep $n2 $n1/dump.txt | wc -l)"
    done

    echo
done
