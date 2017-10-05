import unittest

from auctioneer import Auctioneer

class TestAuctioneer(unittest.TestCase):

    def test_init(self):
        Auctioneer(0.5)

    def test_alone(self):
        a = Auctioneer(0.5)
        self.assertEqual(0.5, a.update())

    def test_1node(self):
        a = Auctioneer(0.5)
        offer = a.store('node1', 0.3) 
        self.assertEqual(0.5, offer)

    def test_2nodes_maxed(self):
        a = Auctioneer(0.5)
        a.store('node1', 0.3) 
        offer = a.store('node2', 0.3) 
        self.assertEqual(0.25, offer)

    def test_noupdate(self):
        a = Auctioneer(0.5)
        a.store('node1', 0.3) 
        offer = a.store('node1', 0.3) 
        self.assertIsNone(offer)

from bidder import Bidder

class TestBidder(unittest.TestCase):

    def test_init(self):
        Bidder(0.2)

    def test_alone(self):
        a = Bidder(0.2)
        self.assertEqual(0.2, a.update())

    def test_1node(self):
        a = Bidder(0.2)
        bid = a.store('node1', 0.1) 
        self.assertEqual(0.1, bid)

    def test_2nodes(self):
        a = Bidder(0.2)
        a.store('node1', 0.4) 
        bid = a.store('node2', 0.1) 
        self.assertEqual(0.1, bid)

    def test_noupdate(self):
        a = Bidder(0.2)
        a.store('node1', 0.3) 
        bid = a.store('node1', 0.3) 
        self.assertIsNone(bid)

if __name__ == '__main__':
    unittest.main()
