"""Guarded real-GP event compilation and packaging contracts, no hardware claims."""
# SPDX-License-Identifier: MIT
import importlib.util,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('patch_p4_kws',ROOT/'tools/patch_p4_kws.py')
patcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(patcher)

class WakeWordEditorContract(unittest.TestCase):
 def test_hat_compiles_native_event_with_original_body(self):
  source=b"before\n\t\t} ('whenBroadcastReceived' == op) {\noriginal broadcast branch\nafter"
  changed=patcher.patch('/MicroBlocksCompiler.gp',source)
  self.assertIn(b"('p4WhenWakeWord' == op)",changed)
  self.assertIn(b"instructionsForExpression this '_p4.wake.OkayNabu'",changed)
  self.assertIn(b"array 'recvBroadcast' 1",changed)
  self.assertIn(b'instructionsForCmdList this (nextBlock cmdOrReporter)',changed)
  self.assertIn(b'original broadcast branch',changed)
 def test_runtime_preserves_receiver_chunk_type(self):
  source=b"\tif ('whenBroadcastReceived' == op) { return 6 }\n(not (isOneOf op 'whenButtonPressed' 'whenBroadcastReceived'))"
  result=patcher.patch('/MicroBlocksRuntime.gp',source)
  self.assertIn(b"if ('p4WhenWakeWord' == op) { return 6 }",result)
  self.assertIn(b"'whenBroadcastReceived' 'p4WhenWakeWord'",result)
 def test_changed_or_duplicate_upstream_is_rejected(self):
  for source in [b'new compiler',b"\t\t} ('whenBroadcastReceived' == op) {\n"*2]:
   with self.assertRaises(ValueError):patcher.patch('/MicroBlocksCompiler.gp',source)
 def test_other_gp_sources_remain_unchanged(self):
  raw=b'unchanged native GP source';self.assertEqual(patcher.patch('/Block.gp',raw),raw)

if __name__=='__main__':unittest.main()
