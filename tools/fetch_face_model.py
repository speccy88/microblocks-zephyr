#!/usr/bin/env python3
"""Fetch the pinned official MediaPipe face bundle into ignored build-artifacts."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
from pathlib import Path
import urllib.request
URL='https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
SHA256='64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
def fetch(output):
    if output.is_file() and hashlib.sha256(output.read_bytes()).hexdigest()==SHA256:return
    with urllib.request.urlopen(URL,timeout=60) as response:data=response.read(8*1024*1024)
    if len(data)!=3758596 or hashlib.sha256(data).hexdigest()!=SHA256:raise ValueError('Face bundle hash/size mismatch')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'build-artifacts/pose/face_landmarker.task');a=p.parse_args();fetch(a.output);print('Verified MediaPipe face bundle: '+str(a.output))
