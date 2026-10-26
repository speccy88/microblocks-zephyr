"""Portable JSON dependency, limits and primitive-compatibility contracts."""
# SPDX-License-Identifier: MIT
import hashlib,json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class JSONContract(unittest.TestCase):
 def test_dependency_is_pinned_and_unmodified(self):
  meta=json.loads((ROOT/'dependencies/json.json').read_text())
  self.assertEqual(meta['commit'],'6447536015f3d600f3d65323b10976103b337ca7')
  for name,sha in meta['files'].items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),sha,name)
  self.assertIn('MIT License',(ROOT/'third_party/yyjson/LICENSE').read_text())
 def test_strict_limits_and_no_system_allocator(self):
  config=(ROOT/'common/json/json_config.h').read_text()
  self.assertIn('#define YYJSON_DISABLE_NON_STANDARD 1',config)
  self.assertIn('#define YYJSON_READER_DEPTH_LIMIT 16',config)
  service=(ROOT/'common/json/json_service.c').read_text()
  self.assertIn('YYJSON_READ_NUMBER_AS_RAW',service)
  self.assertNotRegex(service,r'\b(?:malloc|calloc|realloc|free)\s*\(')
  self.assertIn('yyjson_alc_pool_init',service)
 def test_new_primitive_set_appends_and_p4_mapping_survives(self):
  runtime=(ROOT/'tools/prepare_p4_zephyr_runtime.py').read_text()
  self.assertIn("'\\tSoundPrims,\\n\\tJSONPrims,\\n\\tClockPrims,\\n\\tStepPrims,\\n\\tStoragePrims,\\n\\tPrimitiveSetCount'",runtime)
  package=(ROOT/'tools/package_p4_ide.py').read_text()
  self.assertIn("atPut primsets 'p4' (at primsets 'io')",package)
  self.assertIn("atPut primsets 'json' 22",package)
  self.assertIn('Libraries/JSON.ubl',package)
  self.assertIn('json-edit',package)
 def test_library_has_explicit_immutable_edits_and_errors(self):
  text=(ROOT/'integration/JSON.ubl').read_text()
  self.assertIn('assign it back to your variable',text)
  self.assertIn('JSON error: ',text)
  for name in ['get','text','set','remove','append','quote','keys','type','length','valid']:
   self.assertIn('[json:'+name+']',text)
  self.assertNotIn('[p4:',text)
if __name__=='__main__':unittest.main()
