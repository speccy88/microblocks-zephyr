#!/usr/bin/env python3
"""Build a local touch editor; preserve all pinned upstream engine bytes."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
from mobile_editor_source import MANIFEST, ROOT, read_editor

BOARDS = {'waveshare': 'rlcd', 'fruit-jam': 'fruit-jam', 'xrp-rp2350': 'xrp'}


def mobile_files(source, runtime='pages', board=None, desktop='../?layout=desktop'):
    if runtime not in ('pages', 'board') or (runtime == 'board' and board not in BOARDS):
        raise ValueError('Unsupported mobile runtime or board')
    files = read_editor(source)
    overlays = {name:(ROOT / 'web/js-editor' / name).read_bytes() for name in
        ['iphone-transport.js', 'iphone-gestures.js', 'iphone-bootstrap.js', 'iphone.css', 'THIRD_PARTY_NOTICES.md']}
    overlays.update({name:(ROOT / 'web/mobile' / name).read_bytes() for name in
        ['mobile-browser.js', 'mobile-load.js', 'mobile-entry.js', 'mobile-entry.css']})
    # Pages serves assets with max-age=600. A changed document must request the
    # matching UI bytes even when a returning browser has the prior release.
    # Board URLs stay unchanged for the embedded HTTP parsers.
    def resource_url(name):
        return name + ('?v=' + hashlib.sha256(overlays[name]).hexdigest()[:16] if runtime == 'pages' and name in overlays else '')
    html = files['purejs.html'].decode('utf-8')
    redirect = "if (location.protocol === 'http:') { location.protocol = 'https:'; }"
    anchor = '\t\t<!-- IDE -->\n\t\t<script type="text/javascript" src="ui/ide.js"></script>'
    if html.count(redirect) != 1 or html.count(anchor) != 1 or html.count('window.onload = function () {') != 1:
        raise ValueError('Review changed pinned mobile startup anchors')
    html = html.replace(redirect, '/* Same-origin board HTTP is intentional; browser transport enforces its scope. */')
    html = html.replace('window.onload = function () {', 'window.microblocksMobileStart = function () {')
    html = html.replace(anchor, '\n'.join('<script src="' + name + '"></script>' for name in
        ['iphone-transport.js', 'mobile-browser.js', 'iphone-gestures.js', 'iphone-bootstrap.js', 'mobile-entry.js']) + '\n' + anchor)
    viewport = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'
    if html.count(viewport) != 1:
        raise ValueError('Review changed viewport')
    html = html.replace(viewport, 'width=device-width, initial-scale=1.0, viewport-fit=cover')
    if runtime == 'board':
        html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="/mobile/">')
    html = html.replace('</head>', '<link rel="stylesheet" href="iphone.css">\n<link rel="stylesheet" href="mobile-entry.css">\n</head>')
    for name in ['iphone.css', 'mobile-entry.css']:
        html = html.replace('href="'+name+'"', 'href="'+resource_url(name)+'"')
    # Execute blocking scripts, then deferred scripts, exactly as the pinned
    # document does. One script/CSS request at a time fits the board servers.
    blocking, deferred = [], []
    def script(match):
        attrs, body = match.groups()
        src = re.search(r'\bsrc="([^"]+)"', attrs)
        entry = {'src': resource_url(src[1])} if src else {'inline': body}
        (deferred if re.search(r'\bdefer\b', attrs) else blocking).append(entry)
        return ''
    # Remove the commented developer-script tag before parsing real tags.
    html = re.sub(r'<!--.*?-->', '', html, flags=re.S)
    html = re.sub(r'<script\b([^>]*)>(.*?)</script>', script, html, flags=re.S)
    if len(blocking) < 30 or not deferred:
        raise ValueError('Unexpected mobile script schedule')
    html = re.sub(r'(<link\b[^>]*rel="stylesheet"[^>]*?)\bhref=', r'\1data-mobile-href=', html)
    html = re.sub(r'(<img\b[^>]*?)\bsrc=', r'\1data-mobile-src=', html)
    profile = {'runtime': runtime, 'board': BOARDS.get(board), 'surface': 'mobile',
               'desktop': desktop, 'startupEvent': 'microblocks-mobile-assets'}
    config = json.dumps({'scripts': blocking + deferred, 'profile': profile}, separators=(',', ':')).replace('<', '\\u003c')
    startup = '<script id="mobile-load-config" type="application/json">' + config + '</script>\n<script src="'+resource_url('mobile-load.js')+'"></script>'
    html = html.replace('</body>', startup + '\n</body>')
    if runtime == 'pages':
        html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="default-src \'self\' data: blob:; connect-src \'self\'; script-src \'self\' \'unsafe-inline\' \'unsafe-eval\'; style-src \'self\' \'unsafe-inline\'; object-src \'none\'; base-uri \'self\'">')
    files['index.html'] = html.encode()
    files['microblocks.html'] = files['index.html']
    files.update(overlays)
    files['iphone-boards.json'] = (ROOT / 'web/mobile/board-profiles.json').read_bytes()
    files['source-manifest.json'] = MANIFEST.read_bytes()
    files['licenses/LOCAL-MIT.txt'] = (ROOT / 'LICENSE').read_bytes()
    for name, path in [('Waveshare RLCD 4.2.ubl', 'boards/waveshare_esp32s3_rlcd_4_2/integration/Waveshare_RLCD_4_2.ubl'),
                       ('Fruit Jam.ubl', 'boards/adafruit_fruit_jam/integration/Fruit_Jam.ubl')]:
        files['Libraries/Zephyr/' + name] = (ROOT / path).read_bytes()
    files['files.txt'] = ('\n'.join(sorted(files)) + '\n').encode()
    receipt = {'schema': 1, 'profile': 'mobile-web', 'runtime': runtime, 'board': board,
               'source_commit': json.loads(MANIFEST.read_text())['source_commit'],
               'touch_source_commit': 'e10a5ee90bd2f5b04b6bc9245d806764c3df2483',
               'upstream_engine_modified': False, 'physical_hardware_validated': False,
               'runtime_upgraded': False, 'firmware_images_included': False,
               'files': {p: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for p, b in sorted(files.items())}}
    files['build-manifest.json'] = (json.dumps(receipt, indent=2) + '\n').encode()
    return files, receipt


def package(source, output, **options):
    files, receipt = mobile_files(source, **options)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--runtime', choices=['pages', 'board'], default='pages')
    p.add_argument('--board', choices=BOARDS)
    a = p.parse_args()
    r = package(a.source, a.output, runtime=a.runtime, board=a.board)
    print(json.dumps({k: v for k, v in r.items() if k != 'files'}))
