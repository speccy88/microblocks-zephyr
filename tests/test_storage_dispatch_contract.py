"""Boundaries for the local, unconnected file dispatcher and existing frame codec."""
# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class StorageDispatcherContract(unittest.TestCase):
 def test_portable_core_has_no_hidden_resources(self):
  source='\n'.join((ROOT/'common/storage'/name).read_text() for name in ['storage.c','dispatcher.c','wire.c'])
  self.assertNotRegex(source,r'\b(?:malloc|calloc|realloc|free|fopen|open|fs_open|fs_mount|flash_write|send|recv)\s*\(')
  self.assertNotIn('zephyr/',source)
  header=(ROOT/'common/storage/dispatcher.h').read_text()
  self.assertIn('#define MB_FILES_CHUNK 512',header)
  self.assertIn('#define MB_FILES_IDLE_MS UINT64_C(30000)',header)
 def test_adapter_uses_existing_connection_and_vm_owner(self):
  source=(ROOT/'web/device-files-wire.js').read_text()+(ROOT/'web/device-files-controller.js').read_text()
  self.assertNotRegex(source,r'\b(?:fetch|XMLHttpRequest|WebSocket|indexedDB|localStorage|sessionStorage|navigator|P4Send)\b')
  self.assertIn('constructor({session,send,subscribe})',source)
  package=(ROOT/'tools/package_p4_ide.py').read_text()
  self.assertIn('device-files-wire.js',package)
  self.assertIn('MicroBlocksFilesConnection?.receive(frame)',package)
  self.assertIn('MicroBlocksFilesConnection?.link(connected?write:null)',package)
  prepare=(ROOT/'tools/prepare_p4_zephyr_runtime.py').read_text()
  self.assertIn('cmd <= 217',prepare)
  platform=(ROOT/'boards/waveshare_esp32p4_wifi6/zephyr/src/platform.c').read_text()
  self.assertNotIn('mb_files_wire(',platform)
  self.assertIn('mb_storage_protocol_message(t,n,p,k_uptime_get())',platform)
  for name in ['main.c','hosted_transport.c']:
   self.assertIn('mb_storage_protocol_', (ROOT/'boards/waveshare_esp32p4_wifi6/zephyr/src'/name).read_text())
 def test_both_new_native_sources_are_compiled(self):
  cmake=(ROOT/'boards/waveshare_esp32p4_wifi6/zephyr/CMakeLists.txt').read_text()
  for name in ['storage.c','dispatcher.c','wire.c','storage_primitives.c','controller.c','storage_protocol.c']:
   self.assertIn('${repo}/common/storage/'+name,cmake)
 def test_single_owner_and_physical_limits_are_documented(self):
  doc=(ROOT/'docs/STORAGE_DISPATCH.md').read_text()
  for phrase in ['single execution owner','Tokens are lifecycle guards, not authentication','synthetic host data','without flashing']:
   self.assertIn(phrase,doc)
  header=(ROOT/'common/storage/storage.h').read_text()
  self.assertIn('MB_FILE_REFERENCE_MAX UINT32_C(0x3fffffff)',header)

if __name__=='__main__':unittest.main()
