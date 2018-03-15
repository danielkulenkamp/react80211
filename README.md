Medium access control (MAC) is a fundamental problem in wireless networks.
In ad-hoc wireless networks especially, many of the performance and scaling issues these networks face can be attributed to their use of the core IEEE 802.11 MAC protocol: distributed coordination function (DCF).
Smoothed Airtime Linear Tuning (SALT) is a new contention window tuning algorithm proposed to address some of the deficiencies of DCF in 802.11 ad-hoc networks.
SALT works alongside a new user level and optimized implementation of REACT, a distributed resource allocation protocol, to ensure that each node secures the amount of airtime allocated to it by REACT.
The algorithm accomplishes that by tuning the contention window size parameter that is part of the 802.11 backoff process.
SALT converges more tightly on airtime allocations than a contention window tuning algorithm from previous work and this increases fairness in transmission opportunities and reduces jitter more than either 802.11 DCF or the other tuning algorithm.
REACT and SALT were also extended to the multi-hop flow scenario with the introduction of a new airtime reservation algorithm.
With a reservation in place multi-hop TCP throughput actually increased when running SALT and REACT as compared to 802.11 DCF, and the combination of protocols still managed to maintain its fairness and jitter advantages.
All experiments were performed on a wireless testbed, not in simulation.
