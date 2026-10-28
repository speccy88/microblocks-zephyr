"""Production packaging and security boundary for the disconnected file manager."""
# SPDX-License-Identifier: MIT
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from package_p4_ide import media_assets,build

class DeviceFilesContract(unittest.TestCase):
 def test_production_shared_assets_exclude_fixture(self):
  assets={'unoq-network.js':b'// adapter'}
  html=media_assets(assets,'<head></head>',ROOT)
  for name in ['device-files-core.js','device-files-wire.js','device-files-controller.js','device-files.js','device-files.css']:
   self.assertIn(name,assets);self.assertIn(name+'?v=',html)
  self.assertNotIn('device-files-fixture.js',assets)
  self.assertNotIn('device-files-fixture.js',html)
  self.assertLess(html.index('device-files-core.js'),html.index('device-files.js'))
  self.assertLess(html.index('device-files-wire.js'),html.index('device-files-controller.js'))
  pages=(ROOT/'tools/package_pages.py').read_text()
  self.assertIn('media_assets(',pages)
  self.assertNotIn('file_fixture=True',pages)
 def test_fixture_is_explicit_and_ordered(self):
  assets={'unoq-network.js':b'// adapter'}
  html=media_assets(assets,'<head></head>',ROOT,file_fixture=True)
  self.assertLess(html.index('device-files-core.js'),html.index('device-files-fixture.js'))
  self.assertLess(html.index('device-files-fixture.js'),html.index('device-files.js'))
  temp_root=ROOT/'build-artifacts';temp_root.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='file-contract-',dir=temp_root) as folder:
   self.assertTrue(Path(folder).resolve().is_relative_to(temp_root.resolve()))
   with self.assertRaisesRegex(ValueError,'hosted image'):
    build(Path(folder),Path(folder),ROOT,hosted=True,file_fixture=True)
   (Path(folder)/'device-files-fixture.js').write_text('fixture')
   with self.assertRaisesRegex(ValueError,'clean output directory'):
    build(Path(folder),Path(folder),ROOT)
 def test_ui_has_no_network_or_persistent_browser_storage(self):
  source='\n'.join((ROOT/'web'/name).read_text(encoding='utf-8') for name in ['device-files-core.js','device-files.js','device-files-fixture.js'])
  self.assertNotRegex(source,r'\b(?:fetch|XMLHttpRequest|WebSocket|indexedDB|localStorage|sessionStorage|showOpenFilePicker|showSaveFilePicker)\b')
  self.assertNotRegex(source,r'\b(?:innerHTML|outerHTML|eval|Function)\b')
  self.assertIn("root.location.hostname==='127.0.0.1'",source)
  self.assertIn("root.location.protocol==='http:'",source)
  self.assertRegex(source,r'Browser fixture . not the board')
  self.assertIn("type:'application/octet-stream'",source)
  self.assertIn('URL.revokeObjectURL',source)
  self.assertIn("querySelector('[data-device-project-panel]')",source)
  # Startup ordering is exercised by device_files_ui.test.js; requiring a
  # particular scheduling primitive hid the real browser ready-listener race.
 def test_live_transport_and_backends_are_not_claimed(self):
  source=(ROOT/'web/device-files.js').read_text(encoding='utf-8')
  self.assertIn('Compatible storage firmware is required',source)
  self.assertIn('Connect files',source)
  self.assertIn('epoch!==uiEpoch',source)
  self.assertIn("['Flash','Flash",source);self.assertIn("['SD','SD",source)
  doc=(ROOT/'docs/FILE_MANAGER.md').read_text(encoding='utf-8')
  self.assertIn('not a wire protocol',doc)

if __name__=='__main__':unittest.main()
