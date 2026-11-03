#!/usr/bin/env python3
"""Make the verified JavaScript editor the portal default; retain legacy assets."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
from add_js_preview import files
from js_editor_shared_assets import assets as shared_assets, SCRIPTS as SHARED_SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ['fruit-jam', 'waveshare', 'esp32p4', 'propeller2', 'xrp-rp2350', 'raspberry-pi5', 'microduck', 'unoq']


def promote(site):
    site = Path(site)
    if (site / 'js-portal-manifest.json').exists() or (site / 'legacy').exists():
        raise ValueError('Fresh reviewed site required; refuse to replace a release')
    before = files(site)
    manifest = json.loads((ROOT / 'dependencies/editor-js.json').read_text(encoding='utf-8'))
    hook = (ROOT / 'web/js-portal/editor-parent.js').read_bytes()
    overlays = shared_assets()
    overlay_tags = '\n'.join('<script src="' + name + '?v=' + hashlib.sha256(overlays[name]).hexdigest()[:16] + '"></script>' for name in SHARED_SCRIPTS) + '\n'
    inputs = []
    # Validate every input before writing. The archive is independently verified
    # by prepare_mobile_editor/add_js_preview; verify its engine again here.
    for name in PROFILES:
        folder = site / 'js-preview' / name
        profile = json.loads((folder / 'target-profile.json').read_text())
        if profile['id'] != name or (folder / 'source-manifest.json').read_bytes() != (ROOT / 'dependencies/editor-js.json').read_bytes():
            raise ValueError('Unexpected JavaScript target or source pin')
        for entry in manifest['files']:
            if entry['path'].startswith('engine/') and hashlib.sha256((folder / entry['path']).read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('JavaScript engine changed: ' + entry['path'])
        for entry in ('index.html', 'microblocks.html'):
            raw = (folder / entry).read_text(encoding='utf-8')
            if raw.count('</head>') != 1 or 'editor-parent.js' in raw or 'gp_wasm.js' in raw:
                raise ValueError('Unexpected JavaScript entry')
            anchor = '\t\t<!-- IDE -->\n\t\t<script type="text/javascript" src="ui/ide.js"></script>'
            if raw.count(anchor) != 1:
                raise ValueError('Review SFC JavaScript startup anchor')
            raw = raw.replace(anchor, overlay_tags + anchor)
            inputs.append((folder / entry, raw.replace('</head>', '<script src="editor-parent.js"></script>\n</head>').encode()))
    legacy = (site / 'index.html').read_text(encoding='utf-8')
    if legacy.count('<head>') != 1 or '<base ' in legacy:
        raise ValueError('Unexpected legacy landing entry')
    legacy, count = re.subn(r'src="portal\.js(?:\?[^\"]*)?"', 'src="legacy/portal.js"', legacy)
    if count != 1:
        raise ValueError('Unexpected legacy portal script')
    (site / 'legacy').mkdir()
    (site / 'legacy/index.html').write_text(legacy.replace('<head>', '<head><base href="../">'), encoding='utf-8', newline='\n')
    (site / 'legacy/portal.js').write_bytes((site / 'portal.js').read_bytes())
    for path, raw in inputs:
        path.write_bytes(raw)
    for name in PROFILES:
        folder = site / 'js-preview' / name
        (folder / 'editor-parent.js').write_bytes(hook)
        for entry, raw in overlays.items():
            target = folder / entry
            if target.exists():
                raise ValueError('Shared editor overlay collides with reviewed input: ' + entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        index = folder / 'files.txt'
        if not index.exists():
            raise ValueError('Reviewed JavaScript file index missing')
        index.write_text('\n'.join(sorted(set(index.read_text().splitlines()) | set(overlays)))+'\n', encoding='utf-8', newline='\n')
        receipt = json.loads((folder / 'build-manifest.json').read_text())
        for entry in ['index.html', 'microblocks.html', 'editor-parent.js', 'files.txt', *overlays]:
            raw = (folder / entry).read_bytes()
            receipt['files'][entry] = {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
        receipt['main_portal_parent_hook'] = True
        receipt['native_sfc_javascript'] = True
        receipt['connected_board_project_readback'] = True
        (folder / 'build-manifest.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
    for name in ['index.html', 'portal.js']:
        (site / name).write_bytes((ROOT / 'web/js-portal' / name).read_bytes())
    html = (site / 'index.html').read_text(encoding='utf-8')
    version = hashlib.sha256((site / 'portal.js').read_bytes()).hexdigest()[:16]
    (site / 'index.html').write_text(html.replace('src="portal.js"', 'src="portal.js?v='+version+'"'), encoding='utf-8', newline='\n')
    after = files(site)
    changed = sorted(name for name, digest in before.items() if after.get(name) != digest)
    allowed = {'index.html', 'portal.js'} | {'js-preview/' + p + '/' + n for p in PROFILES for n in ['index.html','microblocks.html','build-manifest.json','files.txt']}
    if set(changed) != allowed:
        raise ValueError('Unexpected JavaScript portal assembly change')
    report = {'schema':1, 'default_editor':'javascript', 'source_commit':manifest['source_commit'],
        'official_v3_release_verified':False, 'gp_branch_changed':False, 'legacy_entry':'legacy/index.html',
        'physical_hardware_validated':False, 'changed_existing_files':changed,
        'original_files':{n:before[n] for n in changed},
        'preserved_files':{n:d for n,d in before.items() if n not in changed},
        'output_files':{n:d for n,d in after.items() if n not in before or n in changed}}
    (site / 'js-portal-manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return {'default_editor':'javascript', 'profiles':PROFILES, 'preserved_files':len(report['preserved_files']), 'legacy_entry':report['legacy_entry']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site',type=Path,required=True)
    print(json.dumps(promote(p.parse_args().site), indent=2))
