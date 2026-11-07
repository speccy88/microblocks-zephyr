#!/usr/bin/env python3
"""Publish the verified JavaScript editor; omit GP from the active artifact."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
from add_js_preview import files
from js_editor_shared_assets import assets as shared_assets, target_assets, SCRIPTS as SHARED_SCRIPTS
from editor_branding import plain_wordmark
from board_installation_pages import load_catalog, render_launcher, guide_assets

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ['fruit-jam', 'waveshare', 'esp32p4', 'propeller2', 'xrp-rp2350', 'raspberry-pi5', 'microduck', 'unoq']


def promote(site):
    site = Path(site)
    catalog = load_catalog(PROFILES)
    if (site / 'js-portal-manifest.json').exists() or (site / 'legacy').exists():
        raise ValueError('Fresh reviewed site required; refuse to replace a release')
    before = files(site)
    # Only the freshly verified build output is pruned. Historical sources,
    # archives, Git refs and local browser/project stores are not touched.
    omitted = {n: d for n, d in before.items() if n.startswith(('editor/', 'preview/')) or n in
               {'portal-adapter.js', 'portal-core.js', 'build-manifest.json', 'linux-preview-manifest.json', '.portal-build'}}
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
            raw = plain_wordmark(raw).replace(anchor, overlay_tags + anchor)
            inputs.append((folder / entry, raw.replace('</head>', '<script src="editor-parent.js"></script>\n</head>').encode()))
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
        local_target = target_assets(name)
        for entry, raw in local_target.items():
            (folder / entry).parent.mkdir(parents=True, exist_ok=True)
            (folder / entry).write_bytes(raw)
        if local_target:
            profile = json.loads((folder / 'target-profile.json').read_text())
            source = json.loads(local_target['target-library-source.json'])
            peripherals = json.loads(local_target['optional-peripherals.json'])
            profile.update(function_names=source['function_names'], auto_load_target_blocks=True,
                           target_library_module=source['modules'][0], target_library_modules=source['modules'],
                           legacy_target_library_module=source['legacy_module'], target_library_owners=source['selector_libraries'],
                           target_library_dependencies=source['library_dependencies'],
                           target_library_sha256=source['sha256'],
                           required_extension_revision=source['required_extension_revision'])
            profile.update(optional_target_library_modules=peripherals['modules'],
                           optional_extension_revision=peripherals['required_extension_revision'])
            (folder / 'target-profile.json').write_text(json.dumps(profile, indent=2)+'\n', encoding='utf-8', newline='\n')
            config = (folder / 'target-config.js').read_text(encoding='utf-8')
            config, count = re.subn(r'const MicroBlocksJSProfile = Object\.freeze\(\{[^\n]*\}\);',
                                   lambda _: 'const MicroBlocksJSProfile = Object.freeze(' + json.dumps(profile, separators=(',', ':')) + ');', config)
            if count != 1:
                raise ValueError('Review changed runtime target profile')
            (folder / 'target-config.js').write_text(config, encoding='utf-8', newline='\n')
            version = hashlib.sha256(config.encode()).hexdigest()[:16]
            for entry in ['index.html', 'microblocks.html']:
                path = folder / entry
                html = path.read_text(encoding='utf-8')
                if html.count('src="target-config.js"') != 1:
                    raise ValueError('Review changed runtime profile script')
                path.write_text(html.replace('src="target-config.js"', 'src="target-config.js?v=' + version + '"'), encoding='utf-8', newline='\n')
        index = folder / 'files.txt'
        if not index.exists():
            raise ValueError('Reviewed JavaScript file index missing')
        index.write_text('\n'.join(sorted(set(index.read_text().splitlines()) | set(overlays) | set(local_target)))+'\n', encoding='utf-8', newline='\n')
        receipt = json.loads((folder / 'build-manifest.json').read_text())
        for entry in ['index.html', 'microblocks.html', 'editor-parent.js', 'files.txt', *overlays, *local_target, *(['target-config.js'] if local_target else [])]:
            raw = (folder / entry).read_bytes()
            receipt['files'][entry] = {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
        if local_target:
            raw = (folder / 'target-profile.json').read_bytes()
            receipt['files']['target-profile.json'] = {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
        receipt['main_portal_parent_hook'] = True
        receipt['native_sfc_javascript'] = True
        receipt['connected_board_project_readback'] = True
        (folder / 'build-manifest.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
    for name in ['index.html', 'portal.js', 'portal.css']:
        (site / name).write_bytes((ROOT / 'web/js-portal' / name).read_bytes())
    html = render_launcher((site / 'index.html').read_text(encoding='utf-8'), catalog)
    version = hashlib.sha256((site / 'portal.js').read_bytes()).hexdigest()[:16]
    css_version = hashlib.sha256((site / 'portal.css').read_bytes()).hexdigest()[:16]
    (site / 'index.html').write_text(html.replace('src="portal.js"', 'src="portal.js?v='+version+'"').replace('href="portal.css"', 'href="portal.css?v='+css_version+'"'), encoding='utf-8', newline='\n')
    for name, raw in guide_assets(catalog, css_version).items():
        path = site / name
        if path.exists():
            raise ValueError('Installation guide collides with reviewed input: ' + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    for name in omitted:
        target = (site / name).resolve()
        if not target.is_relative_to(site.resolve()):
            raise ValueError('Refuse to omit a file outside the generated site')
        target.unlink()
    for prefix in ['editor', 'preview']:
        folder = site / prefix
        if folder.exists():
            for child in sorted((p for p in folder.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                child.rmdir()
            folder.rmdir()
    after = files(site)
    changed = sorted(name for name, digest in before.items() if after.get(name) != digest)
    allowed = {'index.html', 'portal.js', 'portal.css'} | {'js-preview/' + p + '/' + n for p in PROFILES for n in ['index.html','microblocks.html','build-manifest.json','files.txt']}
    allowed |= {'js-preview/propeller2/' + n for n in target_assets('propeller2') if 'js-preview/propeller2/' + n in before}
    allowed.add('js-preview/propeller2/target-profile.json')
    allowed.add('js-preview/propeller2/target-config.js')
    allowed |= set(omitted)
    if set(changed) != allowed:
        raise ValueError('Unexpected JavaScript portal assembly change')
    report = {'schema':1, 'default_editor':'javascript', 'source_commit':manifest['source_commit'],
        'official_v3_release_verified':False, 'gp_branch_changed':False, 'legacy_entry':None,
        'gp_editor_published':False, 'omitted_gp_files':omitted,
        'physical_hardware_validated':False, 'changed_existing_files':changed,
        'original_files':{n:before[n] for n in changed},
        'preserved_files':{n:d for n,d in before.items() if n not in changed},
        'output_files':{n:d for n,d in after.items() if n not in before or n in changed}}
    (site / 'js-portal-manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return {'default_editor':'javascript', 'profiles':PROFILES, 'preserved_files':len(report['preserved_files']), 'legacy_entry':None, 'omitted_gp_files':len(omitted)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site',type=Path,required=True)
    print(json.dumps(promote(p.parse_args().site), indent=2))
