#!/usr/bin/env python3
"""Prepare an auditable, unpublished ARM64 candidate from retained Pi evidence.

No network, compilation, execution, installation, tag or publication occurs.
The report is evidence to audit, not a cryptographic runtime attestation.
"""
# SPDX-License-Identifier: MIT
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'linux/arm64'
sys.path.insert(0, str(NATIVE))
from build import prepare, COMMIT  # noqa: E402

spec = importlib.util.spec_from_file_location('arm64_package', NATIVE / 'package.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def archive_bytes(entries, epoch):
    output = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=epoch) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as bundle:
            for name, raw in sorted(entries.items()):
                path = PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts or str(path) != name or '\\' in name:
                    raise ValueError('Unsafe corresponding-source path')
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                info.mtime = epoch
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mode = 0o755 if name.endswith('/build.sh') else 0o644
                bundle.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def verify_evidence(binary, source_manifest, report):
    if (len(binary) < 64 or len(binary) > 32 * 1024 * 1024 or binary[:6] != b'\x7fELF\x02\x01'
            or struct.unpack_from('<H', binary, 18)[0] != 183):
        raise ValueError('Expected an ELF64 AArch64 binary')
    if report.get('result') != 'PASS' or report.get('source_commit') != COMMIT:
        raise ValueError('A passing native report for the pinned upstream is required')
    if report.get('host', {}).get('architecture') != 'aarch64' or report['host'].get('sanitizers') is not False:
        raise ValueError('An ordinary native AArch64 report is required')
    if report.get('binary_sha256') != digest(binary):
        raise ValueError('Binary differs from the native execution report')
    protocol = report.get('protocol', {})
    if protocol.get('result') != 'PASS' or protocol.get('architecture') != 'aarch64' or protocol.get('binary_sha256') != digest(binary):
        raise ValueError('Passing native interpreter protocol evidence must match the binary')
    if report.get('self_test', {}).get('result') != 'PASS' or report['self_test'].get('architecture') != 'aarch64':
        raise ValueError('Passing native self-test evidence is required')
    if source_manifest.get('sanitize') is not False or source_manifest.get('source_commit') != COMMIT:
        raise ValueError('Source manifest must describe the ordinary pinned build')
    if not source_manifest.get('sources') or report['host'].get('source_hashes_verified') != len(source_manifest['sources']):
        raise ValueError('Native source count does not match the prepared manifest')


def committed_inputs(commit):
    """Read only native build/packaging inputs from the immutable port commit."""
    roots = ['linux/arm64', 'dependencies/smallvm-v417.json', 'dependencies/json.json',
             'third_party/yyjson', 'common/json/json_config.h',
             'scripts/install-smallvm-linux-arm64.sh', 'scripts/uninstall-smallvm-linux-arm64.sh',
             'tools/prepare_linux_arm64_release.py', 'tests/linux_arm64_protocol.py']
    paths = git('ls-tree', '-rz', '--name-only', commit, '--', *roots).split(b'\0')
    selected, checkout = {}, {}
    for raw in paths:
        if not raw:
            continue
        name = raw.decode('utf-8')
        # Tests/evidence are retained separately; only actual recipe inputs here.
        if '/tests/' in name or Path(name).suffix in {'.png', '.pyc'}:
            continue
        expected = git('show', commit + ':' + name)
        actual = ROOT / name
        if actual.is_symlink() or not actual.is_file():
            raise ValueError('Native input differs from port commit: ' + name)
        content = actual.read_bytes()
        if content != expected:
            # Windows checkout conversion is reproducible and must be explicit.
            # Preserve the tested raw bytes; never normalize a tested source.
            if b'\0' in expected or b'\r' in expected or content != expected.replace(b'\n', b'\r\n'):
                raise ValueError('Native input differs from port commit: ' + name)
            checkout[name] = {'conversion': 'LF to CRLF', 'git_sha256': digest(expected),
                              'checkout_sha256': digest(content)}
        selected[name] = content
    # New, untracked native input files would otherwise escape the Git listing.
    for directory in ('linux/arm64/platform', 'linux/arm64/runtime'):
        actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / directory).iterdir() if p.suffix in {'.c', '.h'}}
        if actual != {name for name in selected if name.startswith(directory + '/') and Path(name).suffix in {'.c', '.h'}}:
            raise ValueError('Native input file set differs from port commit')
    return selected, checkout


def prepare_candidate(*, binary_path, manifest_path, report_path, upstream, output, version):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', version) or version == 'latest':
        raise ValueError('Pinned candidate version is required')
    if output.exists():
        raise FileExistsError('Refusing existing candidate output')
    binary = binary_path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    report_raw = report_path.read_bytes()
    manifest, report = json.loads(manifest_raw), json.loads(report_raw)
    verify_evidence(binary, manifest, report)
    commit = git('rev-parse', 'HEAD').decode().strip()
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Immutable port commit is required')
    recipe, checkout = committed_inputs(commit)
    epoch = int(git('show', '-s', '--format=%ct', commit).decode().strip())
    scratch = ROOT / 'build-artifacts/linux-arm64-release-work'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='microblocks-corresponding-', dir=scratch) as temporary:
        staged = Path(temporary) / 'prepared'
        regenerated = prepare(upstream.resolve(), staged, sanitize=False)
        if 'protocol_test_sha256' in manifest:
            protocol = recipe['tests/linux_arm64_protocol.py']
            regenerated['protocol_test_sha256'] = digest(protocol)
            (staged / 'tests').mkdir()
            (staged / 'tests/linux_arm64_protocol.py').write_bytes(protocol)
        if regenerated != manifest:
            raise ValueError('Current committed recipe does not regenerate the tested source manifest')
        (staged / 'source-manifest.json').write_bytes(manifest_raw)
        entries = {'prepared/' + path.relative_to(staged).as_posix(): path.read_bytes()
                   for path in staged.rglob('*') if path.is_file() and path.name != '.linux-arm64-build'}
    provenance = {'port_commit': commit, 'prepared_source_sha256': digest(manifest_raw),
                  'native_report_sha256': digest(report_raw), 'upstream_commit': COMMIT,
                  'binary_sha256': digest(binary), 'scope': 'candidate; unpublished; Pi evidence only; no physical MicroDuck'}
    entries.update({'port/' + name: raw for name, raw in recipe.items()})
    entries['SOURCE-CHECKOUT.json'] = encoded(checkout)
    provenance['checkout_conversions'] = checkout
    entries['PROVENANCE.json'] = encoded(provenance)
    entries['README.txt'] = (b'Corresponding prepared SmallVM Linux ARM64 source.\n'
                           b'On native Linux AArch64: cd prepared; sh build.sh; ./smallvm --self-test\n'
                           b'Includes MPL-2.0 SmallVM source/license and MIT yyjson source/license.\n'
                           b'port/ retains the exact port recipe; regeneration also requires the pinned upstream Git commit.\n'
                           b'No hardware MicroDuck compatibility, OS reboot, service or publication is claimed.\n')
    source_raw = archive_bytes(entries, epoch)
    source_name = 'smallvm-' + version + '-source.tar.gz'
    binary_name = 'smallvm-' + version + '-linux-aarch64.tar.gz'
    package_provenance = {key: provenance[key] for key in ('port_commit', 'prepared_source_sha256', 'native_report_sha256')}
    package_provenance['source_archive_sha256'] = digest(source_raw)
    # All validation happens before publication into a fresh local output folder.
    output.mkdir(parents=True)
    (output / source_name).write_bytes(source_raw)
    binary_sha = packager.package(binary, entries['prepared/LICENSE'], output / binary_name, version,
                                 epoch=epoch, provenance=package_provenance)
    artifacts = {source_name: digest(source_raw), binary_name: binary_sha}
    for name, raw in {'native-report.json': report_raw, 'prepared-source-manifest.json': manifest_raw,
                      'install-smallvm-linux-arm64.sh': recipe['scripts/install-smallvm-linux-arm64.sh'],
                      'uninstall-smallvm-linux-arm64.sh': recipe['scripts/uninstall-smallvm-linux-arm64.sh']}.items():
        (output / name).write_bytes(raw)
        artifacts[name] = digest(raw)
    candidate = dict(provenance, version=version, architecture='linux-aarch64', available=False,
                     published=False, source_archive_sha256=digest(source_raw), artifacts=artifacts,
                     limitations=['User-service and OS reboot acceptance pending', 'No physical MicroDuck',
                                  'No other ARM64 board tested', 'No published installer or Pages acceptance'])
    candidate_raw = encoded(candidate)
    (output / 'candidate.json').write_bytes(candidate_raw)
    artifacts['candidate.json'] = digest(candidate_raw)
    (output / 'SHA256SUMS').write_text(''.join(f'{value}  {name}\n' for name, value in sorted(artifacts.items())), encoding='ascii')
    return candidate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('binary', 'manifest', 'report', 'upstream', 'output'):
        parser.add_argument('--' + flag, required=True, type=Path)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    result = prepare_candidate(binary_path=args.binary, manifest_path=args.manifest, report_path=args.report,
                               upstream=args.upstream, output=args.output, version=args.version)
    print(json.dumps({'candidate_directory': str(args.output), 'port_commit': result['port_commit'],
                      'binary_sha256': result['binary_sha256'], 'published': False}, indent=2))
