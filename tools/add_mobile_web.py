#!/usr/bin/env python3
"""Add the touch subtree and a narrow landing-page offer to the reviewed site."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
from add_js_preview import files
from package_mobile_editor import ROOT, package


def entry_tags(config, prefix=''):
    assets = [ROOT / 'web/mobile/mobile-entry.js', ROOT / 'web/mobile/mobile-entry.css']
    version = hashlib.sha256(b''.join(p.read_bytes() for p in assets)).hexdigest()[:16]
    raw = json.dumps(config, separators=(',', ':')).replace('<', '\\u003c')
    return ('<script id="mobile-layout-config" type="application/json">' + raw + '</script>\n' +
            '<link rel="stylesheet" href="' + prefix + 'mobile-entry.css?v=' + version + '">\n' +
            '<script src="' + prefix + 'mobile-entry.js?v=' + version + '" defer></script>\n')


def add(site):
    site = Path(site)
    before = files(site)
    if 'mobile/index.html' in before or 'mobile-web-manifest.json' in before:
        raise ValueError('Fresh site required; refuse to replace a mobile release')
    source = site / 'js-preview/waveshare'
    receipt = package(source, site / 'mobile')
    html = (site / 'index.html').read_text(encoding='utf-8')
    anchor = r'(<script\b[^>]*\bsrc="portal\.js(?:\?[^"]*)?"[^>]*>)'
    if len(re.findall(anchor, html)) != 1:
        raise ValueError('Review changed portal entry script')
    if '<iframe' in html or html.count('class="board-choice"') != 8:
        raise ValueError('Review changed direct editor launcher')
    html = re.sub(anchor, lambda m: entry_tags({'surface': 'launcher', 'mobile': 'mobile/index.html', 'desktop': './?layout=desktop'}) + m[0], html)
    (site / 'index.html').write_text(html, encoding='utf-8', newline='\n')
    for name in ['mobile-entry.js', 'mobile-entry.css']:
        (site / name).write_bytes((ROOT / 'web/mobile' / name).read_bytes())
    after = files(site)
    if any(after.get(name) != digest for name, digest in before.items() if name != 'index.html'):
        raise ValueError('Existing desktop or preview asset changed')
    added = set(after) - set(before)
    if any(not n.startswith('mobile/') and n not in ['mobile-entry.js', 'mobile-entry.css'] for n in added):
        raise ValueError('Unexpected mobile composition path')
    report = {'schema': 1, 'base_main_commit': '622c0c09fd0ad942f34048806629c0dd7a62c045',
              'editor_source_commit': receipt['source_commit'], 'touch_source_commit': receipt['touch_source_commit'],
              'changed_existing_files': ['index.html'], 'preserved_existing_files': {n: d for n, d in before.items() if n != 'index.html'},
              'original_landing_sha256': before['index.html'], 'landing_sha256': after['index.html'],
              'added_files': {n: after[n] for n in sorted(added)}, 'physical_hardware_validated': False,
              'board_connection_from_pages': False, 'deployment_performed': False}
    (site / 'mobile-web-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return {'preserved_files': len(before) - 1, 'added_files': len(added), 'changed_existing_files': ['index.html']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(add(a.site), indent=2))
