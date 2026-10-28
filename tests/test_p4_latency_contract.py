"""Latency observation cannot reconfigure RF or turn into a normal control API."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/'boards/waveshare_esp32p4_wifi6/zephyr'
class LatencyObservation(unittest.TestCase):
 def test_profile_is_opt_in(self):
  option=(BOARD/'Kconfig').read_text().split('config P4_WIFI_LATENCY_DIAGNOSTIC\n')[1].split('\nconfig ')[0]
  self.assertIn('default n',option)
  for path in (BOARD/'profiles').glob('*.conf'):
   if path.name!='wifi-latency-diagnostic.conf':self.assertNotIn('CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC=y',path.read_text())
 def test_power_save_is_read_only_USB_and_bounded(self):
  branch=(BOARD/'src/network_backend.c').read_text().split('else if(op==9&&')[1].split('\n#endif')[0]
  self.assertIn('p4_transport_is_usb()',branch)
  self.assertIn('reads<3',branch)
  self.assertIn('net_mgmt(NET_REQUEST_WIFI_PS_CONFIG,',branch)
  self.assertNotIn('NET_REQUEST_WIFI_PS,',branch)
  self.assertNotIn('WifiSetPs',branch)
 def test_snapshot_has_no_payload_or_network_identifiers(self):
  body=(BOARD/'src/hosted_transport.c').read_text().split('void p4_transport_latency_json(')[1].split('\n#else')[0]
  for forbidden in ['password','ssid','payload','address','mac_addr']:self.assertNotIn(forbidden,body)
if __name__=='__main__':unittest.main()
