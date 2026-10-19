"""Host client interoperability vectors; no serial port is opened."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('network_setup_client',Path(__file__).resolve().parents[1]/'tools/network_setup_client.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)

class NetworkClientVectors(unittest.TestCase):
    def test_probe_wire_vector_matches_common_protocol(self):
        self.assertEqual(client.encode(1,0x01020304),bytearray.fromhex('fbcd000b004d424e57020104030201fe'))

    def test_full_length_connection_stays_inside_runtime_guard(self):
        packet=client.encode(2,9,b'S'*32,b'a'*64,True)
        self.assertEqual(len(packet),115)
        self.assertEqual(packet[3:5],b'\x6e\x00')
        self.assertEqual(packet[15:18],bytes([1,32,64]))
        self.assertEqual(packet[-1],254)

    def test_keys_are_not_accepted_on_status_and_invalid_key_never_encoded(self):
        for op,ssid,key,remember in ((3,b'x',b'12345678',False),(1,None,None,True),
                                     (2,b'x',b'g'*64,False),(2,b'x',b'bad\0key!',False)):
            with self.assertRaises(ValueError):client.encode(op,1,ssid,key,remember)

    def test_minimum_connection_has_unambiguous_nonremember_flag(self):
        packet=client.encode(2,1,b'x',b'12345678')
        self.assertEqual(packet[15:18],bytes([0,1,8]))
