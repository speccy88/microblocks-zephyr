"""P4's measured LAN opening budget must not change USB or become unbounded."""
from pathlib import Path
import re,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from package_p4_ide import serial_open_wait,heartbeat_wait

class ConnectionOpening(unittest.TestCase):
 def test_USB_keeps_existing_five_second_wait(self):
  code=serial_open_wait().decode()
  self.assertEqual(re.findall(r'< (\d+)\)\)',code),['5000'])
  self.assertIn('waitMSecs 10',code)
 def test_hosted_wait_is_finite_and_cleans_up_only_after_expiry(self):
  code=serial_open_wait(True).decode()
  self.assertEqual(re.findall(r'< (\d+)\)\)',code),['30000'])
  self.assertLess(code.index('while '),code.index('closeSerialPort 1'))
  self.assertLess(code.index('closeSerialPort 1'),code.index('return'))
  self.assertTrue(code.endswith("portName = 'webserial'"))
 def test_hosted_heartbeat_tolerates_measured_success_but_keeps_other_deadlines(self):
  original=b'\tpingTimeout = 8000\ncommandTimeout = 10000\n\tpingTimeout = 8000\n'
  self.assertEqual(heartbeat_wait(original),original)
  hosted=heartbeat_wait(original,True)
  self.assertEqual(hosted.count(b'pingTimeout = 30000'),2)
  self.assertIn(b'commandTimeout = 10000',hosted)
 def test_changed_heartbeat_source_fails_packaging_instead_of_partial_patch(self):
  with self.assertRaises(ValueError):heartbeat_wait(b'\tpingTimeout = 8000',True)
if __name__=='__main__':unittest.main()
