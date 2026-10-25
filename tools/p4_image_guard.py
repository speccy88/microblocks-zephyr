#!/usr/bin/env python3
"""Constrain Zephyr simple-boot ROM header to this pre-v3 P4 board.

Upstream simple-boot emits a RAM-only header with unbounded revision fields.
Only those header fields are tightened; hidden flash segments are preserved.
No digest is appended in this format, and segment checksum excludes the header.
"""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,struct
from pathlib import Path
def guard(data):
 if len(data)<24 or data[0]!=0xe9 or struct.unpack_from('<H',data,12)[0]!=18 or data[23]!=0:
  raise ValueError('Expected ESP32-P4 simple-boot image without appended digest')
 output=bytearray(data)
 struct.pack_into('<HH',output,15,103,199)
 return bytes(output)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 raw=a.source.read_bytes();out=guard(raw);a.output.write_bytes(out)
 print(json.dumps({'minimum_revision':'1.3','maximum_revision':'1.99','input_sha256':hashlib.sha256(raw).hexdigest(),'output_sha256':hashlib.sha256(out).hexdigest(),'bytes':len(out)}))
