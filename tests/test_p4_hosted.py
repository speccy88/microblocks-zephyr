"""Reject corrupt editor bundles and destinations outside their partition."""
import hashlib,struct,sys,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from flash_p4_assets import validate_assets
from flash_p4_incremental import changed_sectors

class P4HostedAssets(unittest.TestCase):
 def bundle(self):
  body=b'bounded editor fixture';header=struct.pack('<8sIIII32s8x',b'MBP4AS1\0',1,1,len(body),zlib.crc32(body),hashlib.sha256(body).digest());raw=header+body
  return raw,dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),files=1,offset='0xfe0000',partition_bytes=0x1000000)
 def test_valid_bundle_stays_below_settings(self):
  raw,manifest=self.bundle();report=validate_assets(raw,manifest)
  self.assertLessEqual(int(report['end_exclusive'],16),0x1fe0000)
 def test_corruption_and_truncation_rejected(self):
  raw,manifest=self.bundle()
  for bad in [raw[:63],raw[:-1],raw[:-1]+bytes([raw[-1]^1])]:
   with self.assertRaises(ValueError):validate_assets(bad,manifest)
 def test_other_destinations_and_manifest_rejected(self):
  raw,manifest=self.bundle()
  for key,value in [('offset','0x2000'),('offset','0x1fe0000'),('partition_bytes',0x2000000),('files',2),('sha256','0'*64)]:
   with self.assertRaises(ValueError):validate_assets(raw,dict(manifest,**{key:value}))

class P4Incremental(unittest.TestCase):
 def image(self):
  data=bytearray(16384);data[0]=0xe9;struct.pack_into('<H',data,12,18);struct.pack_into('<HH',data,15,103,199);return data
 def test_preserves_unchanged_sectors(self):
  before=self.image();after=bytearray(before);after[8192]=17
  sectors=changed_sectors(before,after);self.assertEqual([(a,len(d)) for a,d in sectors],[(0x4000,4096)])
  reconstructed=bytearray(before)
  for address,data in sectors:reconstructed[address-0x2000:address-0x2000+len(data)]=data
  self.assertEqual(reconstructed,after)
 def test_rejects_length_revision_and_large_change(self):
  before=self.image();bad=bytearray(before);bad[15]=0
  for after in [before[:23],bad]:
   with self.assertRaises(ValueError):changed_sectors(before,after)
  before.extend(b'\0'*270336);after=bytearray(before);after[4096:]=b'\x01'*(len(after)-4096)
  with self.assertRaises(ValueError):changed_sectors(before,after)
 def test_growth_and_shrink_preserve_other_sectors(self):
  before=self.image();after=before+bytearray(b'new linked tail')
  sectors=changed_sectors(before,after)
  self.assertEqual([(a,len(d)) for a,d in sectors],[(0x6000,4096)])
  reverse=changed_sectors(after,before)
  self.assertEqual(reverse,[(0x6000,b'\xff'*4096)])

if __name__=='__main__':unittest.main()
