#!/usr/bin/env python3
"""Package the pinned experimental JS editor, without changing GP or SmallVM."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
from js_editor_source import load_manifest, verified_files

ROOT = Path(__file__).resolve().parents[1]
REDIRECT = "if (location.protocol === 'http:') { location.protocol = 'https:'; }"
LOCAL_REDIRECT = "if (location.protocol === 'http:' && location.hostname !== '127.0.0.1') { location.protocol = 'https:'; }"
ANCHOR = '\t\t<!-- IDE -->\n\t\t<script type="text/javascript" src="ui/ide.js"></script>'
MICRODUCK_LIBRARIES = ('MicroDuck', 'Head_IMU', 'Depth', 'Gamepad', 'Robot', 'Pad_IMU')
MICRODUCK_BUNDLE = 'Libraries/MicroDuck Linux.ubl'


def microduck_files():
    """One coherent import, with exact separate sources and dependency manifest."""
    result, records = {}, []
    bundle = b'// MicroDuck Linux: six normal gateway libraries. Hardware unvalidated.\n'
    for name in MICRODUCK_LIBRARIES:
        source = 'linux/microduck/' + name + '.ubl'
        data = (ROOT / source).read_bytes()
        destination = 'sources/microduck/' + name + '.ubl'
        result[destination] = data
        records.append({'source_path': source, 'packaged_source': destination,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'bundle_offset': len(bundle)})
        bundle += data + b'\n\n'
    result[MICRODUCK_BUNDLE] = bundle
    result['microduck-libraries.json'] = (json.dumps({'schema': 1, 'bundle': MICRODUCK_BUNDLE,
        'automatic_import': False, 'physical_hardware_validated': False,
        'sources': records}, indent=2) + '\n').encode()
    return result


def package(source, output, manifest_path=None):
    manifest_path = manifest_path or ROOT / 'dependencies/editor-js.json'
    manifest = load_manifest(manifest_path)
    files = verified_files(source, manifest)
    html = files['purejs.html'].decode('utf-8')
    if html.count(REDIRECT) != 1 or html.count(ANCHOR) != 1:
        raise ValueError('Upstream entry point changed; review integration anchors')
    # The original entry point is retained. This generated entry allows only
    # the existing loopback bridge's HTTP origin; remote HTTP still redirects.
    html = html.replace(REDIRECT, LOCAL_REDIRECT).replace(ANCHOR,
        '\t\t<script src="linux-compat.js"></script>\n'
        '\t\t<script src="legacy-slots.js"></script>\n'
        '\t\t<script src="readback-compat.js"></script>\n'
        '\t\t<script src="linux-bootstrap.js"></script>\n' + ANCHOR)
    files['index.html'] = html.encode('utf-8')
    # The existing Linux bridge intentionally serves this fixed entry name.
    files['microblocks.html'] = files['index.html']
    files['linux-compat.js'] = (ROOT / 'web/js-editor/linux-compat.js').read_bytes()
    files['legacy-slots.js'] = (ROOT / 'web/js-editor/legacy-slots.js').read_bytes()
    files['readback-compat.js'] = (ROOT / 'web/js-editor/readback-compat.js').read_bytes()
    files['linux-bootstrap.js'] = (ROOT / 'web/js-editor/bootstrap.js').read_bytes()
    files['licenses/LOCAL-MIT.txt'] = (ROOT / 'LICENSE').read_bytes()
    files['THIRD_PARTY_NOTICES.md'] = (ROOT / 'web/js-editor/THIRD_PARTY_NOTICES.md').read_bytes()
    files['source-manifest.json'] = manifest_path.read_bytes()
    files['matrix-source.json'] = (ROOT / 'dependencies/unoq-matrix-gp.json').read_bytes()
    local = microduck_files()
    if files.keys() & local.keys():
        raise ValueError('Local library path collides with upstream')
    files.update(local)
    # Official MB_Files and its picker require the build-generated file index.
    # Generate it from actual packaged paths; no upstream engine patch needed.
    if 'files.txt' in files:
        raise ValueError('Upstream now provides files.txt; review index generation')
    files['files.txt'] = ('\n'.join(sorted(files)) + '\n').encode()
    receipt = {'schema': 1, 'profile': 'experimental-linux-microduck',
               'source_commit': manifest['source_commit'], 'runtime_upgraded': False,
               'upstream_engine_modified': False, 'graphical_acceptance': False,
               'firmware_images_included': False,
               'files': {p: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
                         for p, b in sorted(files.items())}}
    files['build-manifest.json'] = (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, data in sorted(files.items()):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = package(args.source, args.output)
    print(f"Packaged {len(result['files'])} files from {result['source_commit']}")
