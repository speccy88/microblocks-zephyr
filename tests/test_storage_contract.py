"""Storage integration limits; behavior is exercised by the host sanitizer test."""
# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class StorageContract(unittest.TestCase):
 def test_core_has_no_external_filesystem_or_allocator(self):
  text=(ROOT/'common/storage/storage.c').read_text()
  self.assertNotRegex(text,r'\b(?:malloc|calloc|realloc|free|fopen|open|fs_open|fs_mount|flash_write|send|recv)\s*\(')
  self.assertNotIn('zephyr/',text)
  for symbol,value in [('MB_FILE_COUNT',8),('MB_FILE_BYTES',8192),('MB_FILE_CHUNK',1024)]:
   self.assertIn(f'#define {symbol} {value}',(ROOT/'common/storage/storage.h').read_text())
 def test_appended_namespace_and_stop_preserves_files(self):
  package=(ROOT/'tools/package_p4_ide.py').read_text()
  for name,index in [('json',22),('clock',23),('steps',24),('storage',25)]:
   self.assertIn(f"atPut primsets '{name}' {index}",package)
  self.assertIn("atPut primsets 'p4' (at primsets 'io')",package)
  self.assertIn('mb_storage_stop();',(ROOT/'boards/waveshare_esp32p4_wifi6/zephyr/src/platform.c').read_text())
  self.assertIn('mb_store_stop(&files)',(ROOT/'common/storage/storage_primitives.c').read_text())
 def test_separate_library_and_explicit_example(self):
  library=(ROOT/'integration/Storage.ubl').read_text()
  self.assertIn('Flash and SD are unavailable',library)
  self.assertIn('disappear on reboot or power loss',library)
  self.assertNotIn('[p4:',library)
  example=(ROOT/'integration/ram-file.ubp').read_text()
  self.assertIn("'/RAM/note.txt'",example)
  self.assertIn('storageWait write',example)
  self.assertNotRegex(example,r'(?i)format|camera|capture|microphone|delete|http|gpio|motor|servo')
if __name__=='__main__':unittest.main()
