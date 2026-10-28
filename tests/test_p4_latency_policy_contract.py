from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];BOARD=ROOT/'boards/waveshare_esp32p4_wifi6/zephyr'
class LowLatencyPolicy(unittest.TestCase):
 def test_explicit_profile_and_default_off(self):
  option=(BOARD/'Kconfig').read_text().split('config P4_WIFI_LOW_LATENCY\n')[1].split('\nconfig ')[0]
  self.assertIn('default n',option);self.assertIn('depends on P4_WIFI_SAVED_BOOT',option)
  for p in (BOARD/'profiles').glob('*.conf'):
   if p.name!='wifi-low-latency.conf':self.assertNotIn('CONFIG_P4_WIFI_LOW_LATENCY=y',p.read_text())
 def test_only_read_api_is_exposed_and_request_is_after_station_ready(self):
  text=(BOARD/'src/network_backend.c').read_text()
  self.assertGreater(text.index('apply_latency_policy(iface);'),text.index('connected=true;phase="ready"'))
  branch=text.split('else if(op==11&&')[1].split('\n#endif')[0]
  self.assertNotIn('net_mgmt',branch);self.assertNotIn('apply_latency_policy',branch)
if __name__=='__main__':unittest.main()
