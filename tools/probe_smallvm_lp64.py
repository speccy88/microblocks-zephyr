#!/usr/bin/env python3
"""Reproduce pinned SmallVM's LP64 rejection and test upstream GP's offset model.

No fetching, source patching, hardware access, software installation or VM
bytecode execution. Run on an LP64 Linux host with GCC and a local upstream Git
repository containing the pinned commit. Output is experimental evidence only.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '2071df569623ba9cdcd6f8106b61796e047df38b'
FILES = {
    'vm/mem.h': 'mem.h',
    'vm/mem.c': 'mem.c',
    'vm/interp.h': 'interp.h',
    'vm/boardHooks.h': 'boardHooks.h',
    'chromeApp/emscripten/mem.h': 'gp_mem.h',
    'linux+pi/buildVMLinux.sh': 'buildVMLinux.sh',
    'linux+pi/buildVMRaspberryPi.sh': 'buildVMRaspberryPi.sh',
}


def run(command, cwd, *, expect_success=True):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30)
    if expect_success and result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(command) + '\n' + result.stdout + result.stderr)
    return result


def probe(upstream, output, compiler='gcc'):
    if platform.system() != 'Linux':
        raise RuntimeError('Run under native LP64 Linux or WSL; this does not claim ARM64 execution.')
    compiler_path = shutil.which(compiler)
    if not compiler_path:
        raise RuntimeError('C compiler unavailable: ' + compiler)
    output.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'dependencies/smallvm-v417.json').read_text(encoding='utf-8'))
    assert lock['canonical_commit'] == COMMIT
    expected = {item['path']: item['sha256'] for item in lock['files']}
    sources = {}
    with tempfile.TemporaryDirectory(prefix='lp64-probe-', dir=output) as folder:
        work = Path(folder)
        for source, name in FILES.items():
            result = subprocess.run(['git', '-c', 'safe.directory=' + str(upstream), '-C', str(upstream),
                                     'show', COMMIT + ':' + source], capture_output=True, timeout=30)
            if result.returncode:
                raise RuntimeError('Pinned upstream file unavailable: ' + source)
            digest = hashlib.sha256(result.stdout).hexdigest()
            if source in expected and digest != expected[source]:
                raise RuntimeError('Pinned VM source hash mismatch: ' + source)
            (work / name).write_bytes(result.stdout)
            sources[source] = {'sha256': digest, 'bytes': len(result.stdout)}
        for name in ('smallvm_lp64_probe.c', 'gp_lp64_reference_probe.c'):
            payload = (ROOT / 'tests' / name).read_bytes()
            (work / name).write_bytes(payload)
            sources['tests/' + name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
        version = run([compiler_path, '--version'], work).stdout.splitlines()[0]
        smallvm_command = [compiler_path, '-std=c11', '-O0', '-Wall', '-Wextra', '-I.',
                           'smallvm_lp64_probe.c', 'mem.c', '-o', 'smallvm-lp64-probe']
        build = run(smallvm_command, work)
        smallvm = json.loads(run([str(work / 'smallvm-lp64-probe')], work).stdout)
        if not smallvm['mem_init_panic_observed'] or smallvm['result'] != 'EXPECTED_REJECTION':
            raise RuntimeError('Unmodified SmallVM unexpectedly accepted the LP64 host')
        guard_source = '#include "mem.h"\n_Static_assert(sizeof(OBJ) == 4, "SMALLVM_REQUIRES_32_BIT_OBJ");\n'
        (work / 'guard.c').write_text(guard_source, encoding='utf-8', newline='\n')
        guard = run([compiler_path, '-std=c11', '-I.', '-c', 'guard.c', '-o', 'guard.o'], work, expect_success=False)
        if guard.returncode == 0 or 'SMALLVM_REQUIRES_32_BIT_OBJ' not in guard.stderr:
            raise RuntimeError('Expected 32-bit object compile guard was not observed')
        gp_command = [compiler_path, '-std=c11', '-O0', '-Wall', '-Wextra', '-I.',
                      'gp_lp64_reference_probe.c', '-o', 'gp-lp64-reference-probe']
        gp_build = run(gp_command, work)
        gp = json.loads(run([str(work / 'gp-lp64-reference-probe')], work).stdout)
        report = {
            'tested_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_repository': 'https://codeberg.org/MicroBlocks/smallvm',
            'source_commit': COMMIT,
            'host': {'system': platform.system(), 'machine': platform.machine(), 'compiler': version},
            'smallvm': smallvm, 'compile_guard': {'expected_rejection': True, 'diagnostic': guard.stderr},
            'gp_offset_reference': gp, 'sources': sources,
            'compile_commands': [smallvm_command, gp_command],
            'smallvm_compiler_diagnostics': build.stderr,
            'gp_compiler_diagnostics': gp_build.stderr,
            'scope': 'LP64 host layout/startup and GP reference macros only; no ARM64 VM, Pi or robot execution',
        }
    destination = output / 'smallvm-lp64-probe.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'build-artifacts/lp64-probe')
    parser.add_argument('--compiler', default='gcc')
    args = parser.parse_args()
    result = probe(args.upstream.resolve(), args.output.resolve(), args.compiler)
    print(json.dumps({key: result[key] for key in ('host', 'smallvm', 'gp_offset_reference', 'scope')}, indent=2))
