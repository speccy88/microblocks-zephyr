#!/usr/bin/env python3
"""Build the native VM with production headless cleanup; no simulated execution."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys


def prepare(linux_source, upstream, output, sanitize=False):
    module_dir = linux_source / 'linux/arm64'
    sys.path.insert(0, str(module_dir.resolve()))
    spec = importlib.util.spec_from_file_location('pinned_mobile_vm_build', module_dir / 'build.py')
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
    report = build.prepare(upstream.resolve(), output.resolve(), sanitize)
    path = output / 'platform/primitives.c'
    raw = path.read_text(encoding='utf-8')
    if raw.count('if(n==0 && a==NULL)return falseObj;') != 1 or raw.count('OBJ primMBDisplayOff(int n,OBJ *a)') != 1:
        raise ValueError('Review changed production headless shutdown cleanup')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    report['fixture_overlay'] = {'scope': 'headless display-off cleanup outside a task',
        'already_in_base': True, 'source_before_sha256': digest, 'source_after_sha256': digest,
        'arithmetic_or_protocol_simulated': False, 'explicit_hardware_use_supported': False}
    (output / 'source-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--linux-source', type=Path, required=True); p.add_argument('--upstream', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--sanitize', action='store_true')
    p.add_argument('--source-only', action='store_true'); p.add_argument('--test', action='store_true')
    a = p.parse_args(); r = prepare(a.linux_source, a.upstream, a.output, a.sanitize)
    if not a.source_only:
        if platform.system() != 'Linux':
            raise RuntimeError('Compile on Linux or request --source-only')
        subprocess.run(['sh', str(a.output.resolve() / 'build.sh')], check=True)
        if a.test:
            subprocess.run([str(a.output.resolve() / 'smallvm'), '--self-test'], check=True, timeout=30)
        r.update(build_host=platform.machine(), self_test='PASS' if a.test else 'not run',
            binary_sha256=hashlib.sha256((a.output / 'smallvm').read_bytes()).hexdigest())
        (a.output / 'build-manifest.json').write_text(json.dumps(r, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'compiled': not a.source_only, 'fixture_overlay': r['fixture_overlay']}))


if __name__ == '__main__':
    main()
