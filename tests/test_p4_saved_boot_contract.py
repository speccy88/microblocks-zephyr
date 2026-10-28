"""Keep automatic station association opt-in and confined to its P4 profile."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/'boards/waveshare_esp32p4_wifi6/zephyr'
class SavedBootProfile(unittest.TestCase):
 def test_default_profiles_do_not_enable_saved_boot(self):
  for path in (BOARD/'profiles').glob('*.conf'):
   if path.name!='saved-boot.conf':self.assertNotIn('CONFIG_P4_WIFI_SAVED_BOOT=y',path.read_text())
  option=(BOARD/'Kconfig').read_text().split('config P4_WIFI_SAVED_BOOT\n',1)[1].split('\nconfig ',1)[0]
  self.assertIn('depends on P4_WIFI_COMPAT_DIAGNOSTIC',option)
  self.assertIn('default n',option)
 def test_saved_boot_profile_does_not_provision_or_enable_an_AP(self):
  profile=(BOARD/'profiles/saved-boot.conf').read_text()
  self.assertEqual([line for line in profile.splitlines() if line.startswith('CONFIG_')],['CONFIG_P4_WIFI_SAVED_BOOT=y'])
  station=(BOARD/'profiles/station.conf').read_text()
  self.assertIn('CONFIG_WIFI_ESP_HOSTED_MCU_AP_STA_MODE=n',station)
  self.assertIn('CONFIG_NET_DHCPV4_SERVER=n',station)
 def test_loss_retry_and_test_action_are_separate_opt_in_profiles(self):
  self.assertIn('CONFIG_P4_WIFI_LOSS_RETRY=y',(BOARD/'profiles/wifi-loss-retry.conf').read_text())
  self.assertNotIn('CONFIG_P4_WIFI_LOSS_TEST=y',(BOARD/'profiles/wifi-loss-retry.conf').read_text())
  for path in (BOARD/'profiles').glob('*.conf'):
   if path.name!='wifi-loss-test.conf':self.assertNotIn('CONFIG_P4_WIFI_LOSS_TEST=y',path.read_text())
  kconfig=(BOARD/'Kconfig').read_text()
  for name,dependency in [('P4_WIFI_LOSS_RETRY','P4_WIFI_SAVED_BOOT'),('P4_WIFI_LOSS_TEST','P4_WIFI_LOSS_RETRY')]:
   option=kconfig.split('config '+name+'\n',1)[1].split('\nconfig ',1)[0]
   self.assertIn('depends on '+dependency,option);self.assertIn('default n',option)
if __name__=='__main__':unittest.main()
