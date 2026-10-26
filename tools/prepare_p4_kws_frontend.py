#!/usr/bin/env python3
"""Prepare one reviewed upstream OOM fix without editing external TFLM."""
# SPDX-License-Identifier: MIT
import hashlib,json,subprocess
from pathlib import Path

def prepare(dependency,output):
 repo=Path(__file__).resolve().parents[1]
 pin=json.loads((repo/'dependencies/p4-tflm.json').read_text())['source_commit']
 rel='tensorflow/lite/experimental/microfrontend/lib/filterbank_util.c'
 original=subprocess.check_output(['git','-C',str(dependency),'show',pin+':'+rel])
 if (dependency/rel).read_bytes()!=original:raise ValueError('Pinned filterbank source differs from canonical commit')
 before=b'state->channel_weight_starts == NULL || state->channel_widths == NULL ||\n'
 if original.count(before)!=1:raise ValueError('Changed filterbank allocation-check anchor')
 # state->work was allocated but omitted from the error condition. Without
 # this guard a failed allocation reaches FilterbankReset(NULL) during setup.
 changed=original.replace(before,before+b'      state->work == NULL ||\n')
 output.mkdir(parents=True,exist_ok=True);target=output/'filterbank_util_checked.c';target.write_bytes(changed)
 return target,{'upstream_commit':pin,'upstream_source':rel,
  'source_sha256':hashlib.sha256(original).hexdigest(),
  'prepared_sha256':hashlib.sha256(changed).hexdigest(),
  'fix':'Reject NULL filterbank work allocation before resetting state',
  'external_source_modified':False,'upstream_notice_preserved':True}
