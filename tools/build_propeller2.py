#!/usr/bin/env python3
"""Build the recovered native P2 port; never opens a serial port or flashes."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

SOURCES = ['p2Main.c', 'p2IOPrims.c', 'p2OutputPrims.c', 'p2PersistFile.c', 'p2FlashDevice.c',
           'p2SensorPrims.c', 'p2SerialPrims.c']
VM_SOURCES = ['mem.c', 'interp.c', 'runtime.c', 'persist.c', 'dataPrims.c',
              'miscPrims.c', 'varPrims.c', 'tinyJSON.c', 'mbFont.c']
FLAGS = {'eval': 'P2_EVAL_BOARD', 'edge': 'P2_EDGE_BOARD', 'edge32': 'P2_EDGE32MB_BOARD'}


def build(compiler, board, output):
    root = Path(__file__).resolve().parents[1]
    native = root / 'boards/propeller2/native'
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    target = output / ('vm_propeller2_' + board + '.bin')
    command = [str(compiler.resolve()), '-2', '-O1', '-Wall', '-DPARALLAX_P2',
               '-D' + FLAGS[board], '-D_BAUD=115200', '-I../vm', '-o', str(target)]
    command += SOURCES + ['../vm/' + name for name in VM_SOURCES]
    result = subprocess.run(command, cwd=native/'propeller2', capture_output=True, text=True)
    (output/(board+'.log')).write_text(result.stdout+result.stderr, encoding='utf-8', newline='\n')
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    report = dict(board=board, compiler=str(compiler), command=command,
                  bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (output/(board+'.json')).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flexcc', type=Path, required=True)
    parser.add_argument('--board', choices=FLAGS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.flexcc, args.board, args.output), indent=2))
