#!/usr/bin/env python3
"""Offline, immutable Git-blob acquisition for the staged JS editor.

No checkout, network, upstream build script, or filesystem symlink is used.
"""
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import PurePosixPath
import re
import subprocess

REPOSITORY = 'https://codeberg.org/MicroBlocks/smallvm.git'
WEB = 'chromeApp/webapp/'
ALIASES = {'Examples': 'Examples', 'Libraries': 'Libraries', 'img': 'img',
           'translations': 'translations', 'versions': 'gp/runtime/versions'}
OMITTED = {'esp32', 'precompiled'}
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024


def safe_path(name):
    parts = PurePosixPath(name).parts
    if (not name or '\\' in name or ':' in name or name.startswith('/') or
            any(p in ('', '.', '..') for p in name.split('/')) or
            any(ord(c) < 32 for c in name) or not parts):
        raise ValueError('Unsafe source path')
    return name


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], timeout=60)


def tree(source, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('An exact lowercase Git commit is required')
    if git(source, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() != commit:
        raise ValueError('Commit mismatch')
    result = {}
    for record in git(source, 'ls-tree', '-rz', commit).split(b'\0'):
        if not record:
            continue
        meta, name = record.split(b'\t', 1)
        mode, kind, blob = meta.decode('ascii').split()
        result[safe_path(name.decode('utf-8'))] = (mode, kind, blob)
    return result


def blobs(source, objects):
    # A single batch avoids hundreds of git subprocesses. Read only Git objects.
    ids = sorted(set(objects))
    raw = subprocess.run(['git', '-C', str(source), 'cat-file', '--batch'],
                         input=('\n'.join(ids) + '\n').encode(),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         check=True, timeout=60).stdout
    result, offset, total = {}, 0, 0
    for blob in ids:
        end = raw.index(b'\n', offset)
        actual, kind, size = raw[offset:end].decode().split()
        size = int(size)
        total += size
        if actual != blob or kind != 'blob' or size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError('Invalid or excessive Git blob')
        offset = end + 1
        data = raw[offset:offset + size]
        offset += size + 1
        if len(data) != size or raw[offset - 1:offset] != b'\n':
            raise ValueError('Truncated Git object')
        result[blob] = data
    if offset != len(raw):
        raise ValueError('Unexpected Git object data')
    return result


def candidate(source, commit):
    entries = tree(source, commit)
    links = {WEB + k for k in ALIASES.keys() | OMITTED}
    data = blobs(source, [v[2] for k, v in entries.items()
                         if k.startswith(WEB) or k in ('LICENSE', 'Mozilla Public License, version 2.0.html')
                         or any(k == p or k.startswith(p + '/') for p in ALIASES.values())])
    selected = {}
    for path, (mode, kind, blob) in entries.items():
        destination = None
        if path.startswith(WEB):
            destination = path[len(WEB):]
            if mode == '120000':
                if path not in links:
                    raise ValueError('Unreviewed upstream symlink')
                if destination in ALIASES and data[blob].decode() != '../../' + ALIASES[destination]:
                    raise ValueError('Changed upstream alias')
                continue
            if destination in ('microblocks.html', 'gpSupport.js', 'emModule.js', 'emscripten.css', 'sw.js'):
                continue
        elif path in ('LICENSE', 'Mozilla Public License, version 2.0.html'):
            destination = 'licenses/upstream/' + path
        else:
            for alias, prefix in ALIASES.items():
                if path == prefix or path.startswith(prefix + '/'):
                    destination = alias + path[len(prefix):]
                    break
        if destination is None:
            continue
        if mode not in ('100644', '100755') or kind != 'blob':
            raise ValueError('Only regular upstream blobs are allowed')
        selected[safe_path(destination)] = {'source_path': path, 'git_blob': blob,
            'bytes': len(data[blob]), 'sha256': hashlib.sha256(data[blob]).hexdigest()}
    return {'schema': 1, 'source_repository': REPOSITORY, 'source_commit': commit,
            'source_ref_hint': 'dev', 'status': 'experimental migration staging',
            'files': [dict(path=p, **entry) for p, entry in sorted(selected.items())]}


def verified_files(source, manifest):
    if manifest.get('schema') != 1 or manifest.get('source_repository') != REPOSITORY:
        raise ValueError('Unrecognized JS source manifest')
    expected = candidate(source, manifest['source_commit'])
    if expected != manifest:
        raise ValueError('Source manifest differs from exact Git tree')
    data = blobs(source, [f['git_blob'] for f in manifest['files']])
    return {f['path']: data[f['git_blob']] for f in manifest['files']}


def load_manifest(path):
    return json.loads(path.read_text(encoding='utf-8'))
