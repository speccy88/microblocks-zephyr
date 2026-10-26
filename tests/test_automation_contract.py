"""Separation, compiler ABI and bounded logical-example contracts."""
# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class AutomationContract(unittest.TestCase):
 def test_portable_cores_have_no_io_or_heap(self):
  for name in ['clock','steps']:
   text=(ROOT/('common/automation/'+name+'.c')).read_text()
   self.assertNotRegex(text,r'\b(?:malloc|calloc|realloc|free|gpio_pin_set|i2c_write|send|recv)\s*\(')
   self.assertNotIn('zephyr/',text)
  self.assertIn('#define MB_TIMER_COUNT 8',(ROOT/'common/automation/clock.h').read_text())
  self.assertIn('#define MB_TRANSITION_COUNT 24',(ROOT/'common/automation/steps.h').read_text())
 def test_separate_sets_and_stop_all_cleanup(self):
  package=(ROOT/'tools/package_p4_ide.py').read_text()
  for name,index in [('json',22),('clock',23),('steps',24)]:self.assertIn("atPut primsets '"+name+"' "+str(index),package)
  self.assertIn("atPut primsets 'p4' (at primsets 'io')",package)
  self.assertIn('mb_automation_stop();',(ROOT/'boards/waveshare_esp32p4_wifi6/zephyr/src/platform.c').read_text())
 def test_examples_are_bounded_and_logical(self):
  example=(ROOT/'integration/steps-timer.ubp').read_text()
  self.assertIn('repeat 6',example);self.assertIn('clockDeleteTimer timer',example);self.assertTrue(example.rstrip().endswith('stepsStop\n}'))
  self.assertNotRegex(example,r'(?i)gpio|motor|servo|analogWrite|digitalWrite')
  self.assertIn('manual',(ROOT/'integration/Clock_Timers.ubl').read_text().lower())
  self.assertIn('not a safety controller',(ROOT/'integration/Steps_Transitions.ubl').read_text())
if __name__=='__main__':unittest.main()
