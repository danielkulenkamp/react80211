# SALT + REACT on 802.11

This repo contains implementations of three main components:

1. SALT: a 802.11 contention window size tuning mechanism
2. REACT: a distributed resource allocation protocol
3. A multi-hop airtime reservation protocol that leverages SALT+REACT

All three components were developed and tested experimentally as part of my MS in CS thesis work.
See abstract below.

## Abstract

Medium access control (MAC) is a fundamental problem in wireless networks.
In ad-hoc wireless networks especially, many of the performance and scaling issues these networks face can be attributed to their use of the core IEEE 802.11 MAC protocol: distributed coordination function (DCF).
Smoothed Airtime Linear Tuning (SALT) is a new contention window tuning algorithm proposed to address some of the deficiencies of DCF in 802.11 ad-hoc networks.
SALT works alongside a new user level and optimized implementation of REACT, a distributed resource allocation protocol, to ensure that each node secures the amount of airtime allocated to it by REACT.
The algorithm accomplishes that by tuning the contention window size parameter that is part of the 802.11 backoff process.
SALT converges more tightly on airtime allocations than a contention window tuning algorithm from previous work and this increases fairness in transmission opportunities and reduces jitter more than either 802.11 DCF or the other tuning algorithm.
REACT and SALT were also extended to the multi-hop flow scenario with the introduction of a new airtime reservation algorithm.
With a reservation in place multi-hop TCP throughput actually increased when running SALT and REACT as compared to 802.11 DCF, and the combination of protocols still managed to maintain its fairness and jitter advantages.
All experiments were performed on a wireless testbed, not in simulation.

## Getting Started

The code in `testbed/` is intended to be run on the testbed.
In my workflow I would modify that code locally and then sync it up to the testbed using the provided script.
The fabfile is run using fabric locally to setup and coordinate the experiments, and you must install the "old" version of fabric to use this code:

    pip install 'fabric<2.0'

Other scripts in `utils/` require the installation of additional python packages as well.

## Running an experiment

Follow these steps to fun a basic experiment:

1. Reserve your nodes [here](https://www.wilab2.ilabt.iminds.be/reservation/)
2. Use the `mkns.py` script to create an NS file.
   For example if you reserved zotacK1 through zotacK4:
``` utils/mkns.py zotacK1 zotacK2 zotacK3 zotacK4 > ns ```
3. Edit (or create from the template) your node_info.txt file with the list of nodes you reserved
4. Swap your experiment in [here](https://www.wilab2.ilabt.iminds.be/)
5. Setup the experiment by running `fab setup` locally
6. Optionally, run `fab setup_multihop` for multi-hop experiments
7. Run one of `fab exp_*` to run a particular experiment
8. Run `fab stop_exp` to stop the experiment
