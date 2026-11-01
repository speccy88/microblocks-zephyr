#!/usr/bin/env python3
"""Bundle the exact official JS editor with an isolated native iPhone profile."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
from js_editor_source import load_manifest, verified_files
from package_js_editor import ANCHOR, REDIRECT

ROOT = Path(__file__).resolve().parents[1]


def package(source, output):
    manifest_path = ROOT / 'dependencies/editor-js.json'
    manifest = load_manifest(manifest_path)
    files = verified_files(source, manifest)
    html = files['purejs.html'].decode('utf-8')
    if html.count(REDIRECT) != 1 or html.count(ANCHOR) != 1:
        raise ValueError('Upstream entry changed; review iPhone integration anchors')
    # The app uses a bundled custom scheme. Browser preview is loopback-only;
    # production networking is native, with no remote HTTP redirect relaxation.
    redirect = "if (location.protocol === 'http:' && location.hostname !== '127.0.0.1') { location.protocol = 'https:'; }"
    html = html.replace(REDIRECT, redirect).replace(ANCHOR,
        '<script src="iphone-transport.js"></script>\n' +
        '<script src="iphone-gestures.js"></script>\n' +
        '<script src="iphone-bootstrap.js"></script>\n' + ANCHOR)
    viewport = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'
    if html.count(viewport) != 1:
        raise ValueError('Review changed upstream viewport')
    html = html.replace(viewport, 'width=device-width, initial-scale=1.0, viewport-fit=cover')
    html = html.replace('</head>', '<link rel="stylesheet" href="iphone.css">\n</head>')
    files['index.html'] = html.encode()
    files['microblocks.html'] = files['index.html']
    for destination, source_path in {
        'iphone-transport.js': 'web/js-editor/iphone-transport.js',
        'iphone-gestures.js': 'web/js-editor/iphone-gestures.js',
        'iphone-bootstrap.js': 'web/js-editor/iphone-bootstrap.js',
        'iphone.css': 'web/js-editor/iphone.css',
        'iphone-boards.json': 'ios/board-profiles.json',
        'THIRD_PARTY_NOTICES.md': 'web/js-editor/THIRD_PARTY_NOTICES.md',
        'licenses/LOCAL-MIT.txt': 'LICENSE',
        'Libraries/Zephyr/Waveshare RLCD 4.2.ubl': 'boards/waveshare_esp32s3_rlcd_4_2/integration/Waveshare_RLCD_4_2.ubl',
        'Libraries/Zephyr/Fruit Jam.ubl': 'boards/adafruit_fruit_jam/integration/Fruit_Jam.ubl',
    }.items():
        if destination in files:
            raise ValueError('iPhone overlay collides with upstream: ' + destination)
        files[destination] = (ROOT / source_path).read_bytes()
    files['source-manifest.json'] = manifest_path.read_bytes()
    files['files.txt'] = ('\n'.join(sorted(files)) + '\n').encode()
    receipt = {'schema': 1, 'profile': 'experimental-iphone-wifi',
               'source_commit': manifest['source_commit'], 'upstream_engine_modified': False,
               'runtime_upgraded': False, 'physical_iphone_validated': False,
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
    print(json.dumps(package(args.source, args.output), indent=2))
