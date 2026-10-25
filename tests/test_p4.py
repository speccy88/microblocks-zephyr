"""P4 simple-boot revision guard regressions (no serial access)."""
import importlib.util, struct, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p4_image_guard',ROOT/'tools/p4_image_guard.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)

class P4RevisionGuard(unittest.TestCase):
 def image(self):
  data=bytearray((i*37)%256 for i in range(512))
  data[0]=0xe9;struct.pack_into('<H',data,12,18);data[23]=0
  return data
 def test_only_revision_fields_change_hidden_segments_are_preserved(self):
  original=bytes(self.image());result=guard.guard(original)
  self.assertEqual(struct.unpack_from('<HH',result,15),(103,199))
  self.assertEqual(result[:15],original[:15]);self.assertEqual(result[19:],original[19:])
  self.assertEqual(len(result),len(original));self.assertEqual(guard.guard(result),result)
 def test_rejects_other_soc_or_image_layout(self):
  for offset,value in [(0,0),(12,9),(23,1)]:
   data=self.image();data[offset]=value
   with self.assertRaises(ValueError):guard.guard(data)
 def test_rejects_truncated_headers(self):
  for length in [0,1,12,23]:
   with self.assertRaises(ValueError):guard.guard(self.image()[:length])
