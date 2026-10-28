#!/usr/bin/env python3
"""Build current stable editors plus isolated, pinned Linux target previews.

No deployment or credentials. The existing Pages workflow performs publication.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from package_pages_linux_preview import build

ROOT = Path(__file__).resolve().parents[1]
LINUX_COMMIT = '2c060b7f4e9153dd7213d9b7c2a479810577eb51'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linux-repo', type=Path, required=True)
    parser.add_argument('--ide-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stable-commit', help='Exact source identity for an exported inspection build')
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    stable_commit = args.stable_commit or subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    # Archive the exact public commit, independent of any local working changes.
    archive = subprocess.check_output(['git', '-C', str(args.linux_repo.resolve()),
                                       'archive', '--format=tar', LINUX_COMMIT])
    with tempfile.TemporaryDirectory(prefix='pages-linux-', dir=output.parent) as temp:
        work = Path(temp)
        linux = work / 'linux-source'
        linux.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(linux, filter='data')
        adapter = linux / 'web/portal/portal-adapter.js'
        before = adapter.read_bytes()
        anchor = b"  if(profile.connection_enabled===false)notify('XRP development preview:"
        if before.count(anchor) != 1:
            raise ValueError('Pinned placeholder status changed; review the overlay')
        after = before.replace(anchor, b"  if(profile.connection_enabled===false)notify(profile.connection_message||'XRP development preview:")
        adapter.write_bytes(after)
        # Only the temporary exported input changes; neither checkout is edited.
        for source, destination in ((ROOT, work / 'stable-build'), (linux, work / 'linux-build')):
            command = [sys.executable, str(source / 'tools/package_pages.py'),
                       '--ide-source', str(args.ide_source.resolve()), '--output', str(destination)]
            if args.fetch:
                command.append('--fetch')
            subprocess.run(command, check=True)
        report = build(work / 'stable-build', work / 'linux-build', output,
                       stable_commit, LINUX_COMMIT)
        report['linux_source_overlay'] = {
            'path': 'web/portal/portal-adapter.js',
            'base_sha256': hashlib.sha256(before).hexdigest(),
            'patched_sha256': hashlib.sha256(after).hexdigest(),
            'source_main_commit': stable_commit,
            'purpose': 'Use the MicroDuck placeholder status instead of the XRP fallback; transport guards unchanged'}
        (output / 'linux-preview-manifest.json').write_text(
            json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({key: report[key] for key in
                         ('stable_source_commit', 'linux_source_commit', 'preserved_stable_files',
                          'added_preview_profiles', 'linux_source_overlay')}, indent=2))


if __name__ == '__main__':
    main()
