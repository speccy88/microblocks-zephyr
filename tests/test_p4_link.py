import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from p4_link import rate_packet,rate_reply
class LinkTests(unittest.TestCase):
    def test_frame_and_reply_correlation(self):
        wire=rate_packet(1,123,921600)
        self.assertEqual(wire[:5],bytes((251,214,0,17,0)))
        self.assertEqual(wire[-1],254);self.assertEqual(len(wire),22)
        body=struct.pack('<4sBBBBII',b'P4BR',1,2,0,3,123,921600)
        self.assertEqual(rate_reply(body,2,123),(0,3,921600))
        for op,token in [(1,123),(2,999)]:
            with self.assertRaises(ValueError):rate_reply(body,op,token)
        with self.assertRaises(ValueError):rate_reply(body[:-1],2,123)
    def test_unsupported_rates_and_missing_tokens(self):
        for args in [(1,1,1000000),(1,0,921600),(0,0,115200),(3,1,921600),(4,1,115200),(2,1,0),(5,1,115200)]:
            with self.assertRaises(ValueError):rate_packet(*args)
        self.assertEqual(len(rate_packet(0)),22)
        self.assertEqual(len(rate_packet(3,123,115200)),22)
if __name__=='__main__':unittest.main()
