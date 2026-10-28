"""The actual benchmark parser rejects corrupt or incomplete asset responses."""
from pathlib import Path
import gzip,hashlib,socket,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import benchmark_p4_http as probe

class Peer:
 def __init__(self,wire):self.wire=bytearray(wire);self.sent=b'';self.closed=False
 def __enter__(self):return self
 def __exit__(self,*args):self.closed=True
 def settimeout(self,value):assert value==5
 def sendall(self,data):self.sent+=data
 def recv(self,count):
  block=bytes(self.wire[:17]);del self.wire[:17];return block

class HTTPProbe(unittest.TestCase):
 def setUp(self):
  self.raw=b'bounded compressed fixture'*97;self.gz=gzip.compress(self.raw)
  self.asset={'path':'fixture.data','flash_bytes':len(self.gz),'bytes':len(self.raw),'sha256':hashlib.sha256(self.raw).hexdigest()}
 def wire(self,body=None):
  if body is None:body=f'{len(self.gz):x}\r\n'.encode()+self.gz+b'\r\n0\r\n\r\n'
  return b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\nTransfer-Encoding: chunked\r\n\r\n'+body
 def run_peer(self,wire):
  peer=Peer(wire)
  with patch.object(socket,'create_connection',return_value=peer):result=probe.measure('192.0.2.1',self.asset)
  self.assertTrue(peer.closed);return result,peer
 def test_fragmented_headers_chunks_and_gzip_integrity(self):
  result,peer=self.run_peer(self.wire());self.assertTrue(result['hash_match'])
  self.assertEqual(result['compressed_bytes'],len(self.gz));self.assertIn(b'GET /fixture.data HTTP/1.1',peer.sent)
 def test_premature_EOF_is_not_success(self):
  with self.assertRaisesRegex(AssertionError,'premature EOF'):self.run_peer(self.wire()[:-5])
 def test_oversized_chunk_is_rejected(self):
  with self.assertRaises(AssertionError):self.run_peer(self.wire(b'10001\r\n'))
 def test_early_final_chunk_is_rejected(self):
  with self.assertRaises(AssertionError):self.run_peer(self.wire(b'0\r\n\r\n'))
 def test_manifest_body_bound_is_enforced(self):
  self.asset['flash_bytes']=1
  with self.assertRaises(AssertionError):self.run_peer(self.wire())
 def test_decoding_cannot_exceed_manifest_bound(self):
  self.asset['bytes']=16
  with self.assertRaises(AssertionError):self.run_peer(self.wire())
 def test_oversized_headers_are_rejected(self):
  with self.assertRaises(AssertionError):self.run_peer(b'HTTP/1.1 200 OK\r\nX: '+b'x'*16384+b'\r\n\r\n')
 def test_corrupt_decoded_hash_is_rejected(self):
  self.asset['sha256']='0'*64
  with self.assertRaises(AssertionError):self.run_peer(self.wire())
if __name__=='__main__':unittest.main()
