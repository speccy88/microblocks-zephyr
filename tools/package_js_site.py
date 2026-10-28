#!/usr/bin/env python3
"""Add a separate JS preview hub beside an existing GP build; no publication."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from html import escape
from package_js_editor import package, PROFILES, ROOT

HUB = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>JavaScript editor preview</title><style>
body{font:18px system-ui;max-width:850px;margin:4rem auto;padding:0 1rem;line-height:1.6;color:#202634;background:#f5f7fa}
article{background:white;border:1px solid #cbd3df;border-radius:12px;padding:1.5rem;margin:1rem 0}a{color:#075b97}h1,h2{line-height:1.2}
</style><h1>JavaScript editor preview</h1>
<p>Explore the new editor while the current GP editor remains available. This preview does not install firmware or connect automatically.</p>
<!-- TARGETS -->
<p><a href="../index.html" target="_blank" rel="noopener noreferrer">Open the current GP portal</a></p></html>
'''


def hashes(folder):
    result = {}
    for path in sorted(folder.rglob('*')):
        if path.is_symlink():
            raise ValueError('Static input must not contain symlinks')
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def build(source, gp_site, output, profiles=None):
    profiles = tuple(profiles) if profiles is not None else tuple(name for name in PROFILES if name != 'development')
    if not profiles or len(set(profiles)) != len(profiles) or any(name not in PROFILES for name in profiles):
        raise ValueError('Choose distinct supported JavaScript targets')
    if Path(gp_site).is_symlink() or Path(output).is_symlink():
        raise ValueError('Static roots must not be symlinks')
    gp_site, output = Path(gp_site).resolve(), Path(output).resolve()
    if output == gp_site or output in gp_site.parents or gp_site in output.parents:
        raise ValueError('GP input and output must be separate trees')
    if output.exists():
        raise FileExistsError('Choose a new side-by-side output directory')
    if not (gp_site / 'index.html').is_file() or (gp_site / 'js-preview').exists():
        raise ValueError('Expected an existing GP build without a JS preview path')
    original = hashes(gp_site)
    shutil.copytree(gp_site, output)
    preview = output / 'js-preview'
    preview.mkdir()
    entries, cards = {}, []
    for profile in profiles:
        receipt = package(source, preview / profile, profile=profile)
        entries[profile] = {'entry': profile + '/index.html', 'target': receipt['target'],
                             'source_commit': receipt['source_commit']}
        config = PROFILES[profile]
        if profile == 'raspberry-pi5':
            description = 'Standalone Linux SmallVM. No robot services required. Use its local SSH tunnel to connect; hosted WSS acceptance is pending.'
        elif profile == 'microduck':
            description = 'Experimental placeholder for offline editing with six typed service libraries. Connections are disabled; physical robot behavior is unverified.'
        elif profile == 'unoq':
            description = 'Reference library and 13 by 8 matrix input. Offline preview; independent UNO Q firmware and hardware acceptance remain pending.'
        else:
            description = 'Experimental USB editor with an explicit board identity/version check. Load target blocks to import its libraries. JavaScript hardware acceptance remains pending.'
            if profile == 'esp32p4':
                description += ' Inline image/audio views and extended services are still being ported; use GP for the existing implementation.'
        cards.append('<article><h2>' + escape(config['name']) + '</h2><p>' + escape(description) + '</p><a href="' + profile + '/index.html" target="_blank" rel="noopener noreferrer">Open ' + escape(config['name']) + ' JavaScript editor</a></article>')
    (preview / 'index.html').write_text(HUB.replace('<!-- TARGETS -->', '\n'.join(cards)), encoding='utf-8', newline='\n')
    result = hashes(output)
    if any(result.get(name) != digest for name, digest in original.items()):
        raise ValueError('An existing GP asset changed')
    # Reject mixed local adapter/library revisions if an input was edited while
    # the multi-profile build ran. Upstream inputs are immutable Git objects.
    for profile in profiles:
        folder = preview / profile
        for packaged, source_path in {
            'linux-compat.js':'web/js-editor/linux-compat.js',
            'board-transport.js':'web/js-editor/board-transport.js',
            'target-profile.js':'web/js-editor/target-profile.js',
            'linux-bootstrap.js':'web/js-editor/bootstrap.js',
            'legacy-slots.js':'web/js-editor/legacy-slots.js',
            'readback-compat.js':'web/js-editor/readback-compat.js',
            'editor-targets.json':'dependencies/editor-targets.json',
        }.items():
            if (folder / packaged).read_bytes() != (ROOT / source_path).read_bytes():
                raise ValueError('Local source changed during packaging: ' + source_path)
        for manifest_name in ('microduck-libraries.json', 'target-libraries.json'):
            if (folder / manifest_name).exists():
                for entry in json.loads((folder / manifest_name).read_text(encoding='utf-8'))['sources']:
                    if hashlib.sha256((ROOT / entry['source_path']).read_bytes()).hexdigest() != entry['sha256']:
                        raise ValueError('Library changed during packaging: ' + entry['source_path'])
    report = {'schema': 1, 'published': False, 'gp_files_preserved': original,
              'profiles': entries, 'files': result, 'runtime_upgraded': False,
              'upstream_engine_modified': False}
    (preview / 'site-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'gp-site', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    report = build(args.source, args.gp_site, args.output)
    print(json.dumps({'gp_files_preserved': len(report['gp_files_preserved']), 'profiles': report['profiles']}, indent=2))
