"""The optional numeric observation must not become a file/network setter."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/'boards/waveshare_esp32p4_wifi6/zephyr'
class HTTPThroughputContract(unittest.TestCase):
 def test_snapshot_is_USB_read_only(self):
  source=(BOARD/'src/network_backend.c').read_text()
  branch=source.split('else if(op==12&&')[1].split('\n }')[0]
  self.assertIn('p4_transport_is_usb()',branch)
  self.assertIn('p4_asset_timing_json(',branch)
  for forbidden in ['net_mgmt','fs_write','credentials','p4_network_connect']:self.assertNotIn(forbidden,branch)
 def test_snapshot_contains_no_payload_or_identifiers(self):
  source=(BOARD/'src/hosted_server.c').read_text()
  branch=source.split('void p4_asset_timing_json(')[1].split('static void finish_timing')[0]
  for forbidden in ['password','ssid','payload','address','url','client->']:self.assertNotIn(forbidden,branch)
  self.assertIn('k_mutex_lock(&transfers_lock',branch)
 def test_internal_flash_scratch_is_not_returned(self):
  source=(BOARD/'src/hosted_server.c').read_text()
  self.assertIn('flash_scratch[512]',source)
  self.assertIn('flash_area_read(assets,asset->offset+state->offset+copied,flash_scratch,part)',source)
  self.assertIn('memcpy(state->buffer+copied,flash_scratch,part)',source)
  self.assertIn('response->body=state->buffer',source)
 def test_timeouts_pools_and_power_policy_are_untouched(self):
  station=(BOARD/'profiles/station.conf').read_text()
  for setting in ['CONFIG_NET_TCP_MAX_SEND_WINDOW_SIZE=4096','CONFIG_NET_BUF_TX_COUNT=24','CONFIG_HTTP_SERVER_MAX_CLIENTS=4']:
   self.assertIn(setting,station)
 def test_faster_poll_is_explicit_and_bounded(self):
  for path in (BOARD/'profiles').glob('*.conf'):
   contents=path.read_text()
   if path.name=='wifi-low-latency.conf':
    self.assertIn('CONFIG_P4_WIFI_LOW_LATENCY=y',contents)
    self.assertIn('CONFIG_ESP_HOSTED_MCU_EVENT_TASK_POLL_MS=5',contents)
   else:self.assertNotIn('CONFIG_ESP_HOSTED_MCU_EVENT_TASK_POLL_MS=',contents)
if __name__=='__main__':unittest.main()
