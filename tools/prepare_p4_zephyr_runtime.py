#!/usr/bin/env python3
"""Prepare real v417 with bounded shared image preview protocol dispatch."""
# SPDX-License-Identifier: MPL-2.0
import argparse
from pathlib import Path
from prepare_smallvm import prepare
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 prepare(a.source.resolve(),a.output.resolve(),strict_digital_arity=True)
 path=a.output/'vm/runtime.c';text=path.read_text()
 if text.count('(cmd <= 205)')!=2:raise ValueError('Unexpected extension dispatch')
 path.write_text(text.replace('(cmd <= 205)','(cmd <= 206)'),newline='\n')
