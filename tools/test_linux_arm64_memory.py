#!/usr/bin/env python3
"""Compile/run the real offset memory backend natively with ASan and UBSan.

The pinned interp.h supplies exact task/root structures. Interpreter hooks are
simulated; this is memory-backend evidence, not VM or Pi hardware acceptance.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

COMMIT = '2071df569623ba9cdcd6f8106b61796e047df38b'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    runtime = repo / 'linux/arm64/runtime'
    parent = repo / 'build-artifacts/linux-arm64-memory'
    parent.mkdir(parents=True, exist_ok=True)
    headers = {name: subprocess.check_output(['git', '-C', str(args.source.resolve()), 'show', COMMIT + ':vm/' + name])
               for name in ['interp.h', 'boardHooks.h']}
    with tempfile.TemporaryDirectory(dir=parent) as directory:
        work = Path(directory)
        for name, content in headers.items():
            (work / name).write_bytes(content)
        binary = work / 'memory-tests'
        command = [args.cc, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   '-I' + str(runtime), '-I' + str(work), str(runtime / 'arena.c'),
                   str(runtime / 'mem.c'), str(repo / 'tests/linux_arm64_memory.c'), '-o', str(binary)]
        build = subprocess.run(command, capture_output=True, text=True)
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)
        environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        run = subprocess.run([str(binary)], capture_output=True, text=True, env=environment, timeout=30)
        if run.returncode:
            raise RuntimeError(run.stdout + run.stderr)
        negative = {}
        for mode in ['bad-root', 'bad-stack']:
            result = subprocess.run([str(binary), mode], capture_output=True, text=True, env=environment, timeout=5)
            if result.returncode != 1 or 'SmallVM panic:' not in result.stderr or 'Sanitizer' in result.stderr:
                raise RuntimeError('Unsafe failure for ' + mode + ': ' + result.stdout + result.stderr)
            negative[mode] = {'exit_code': result.returncode, 'stderr': result.stderr.strip()}
        report = {
            'result': 'PASS', 'source_commit': COMMIT, 'compiler': args.cc,
            'scope': 'real native LP64 offset arena and compacting GC; interpreter hooks simulated',
            'stdout': run.stdout.strip(), 'negative_tests': negative,
            'sanitizers': ['address', 'undefined'], 'sanitizer_diagnostics': run.stderr,
            'arm64_physical_claim': False,
        }
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
