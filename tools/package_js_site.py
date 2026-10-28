#!/usr/bin/env python3
"""Add a separate JS preview hub beside an existing GP build; no publication."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from package_js_editor import package

HUB = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>JavaScript editor preview</title><style>
body{font:18px system-ui;max-width:850px;margin:4rem auto;padding:0 1rem;line-height:1.6;color:#202634;background:#f5f7fa}
article{background:white;border:1px solid #cbd3df;border-radius:12px;padding:1.5rem;margin:1rem 0}a{color:#075b97}h1,h2{line-height:1.2}
</style><h1>JavaScript editor preview</h1>
<p>Explore the new editor while the current GP editor remains available. This preview does not install firmware or connect automatically.</p>
<article><h2>Raspberry Pi 5</h2><p>Standalone Linux SmallVM. Core editing works without robot services. VM connection uses the Pi-hosted editor through a local SSH tunnel. Hosted WSS acceptance is pending.</p>
<a href="raspberry-pi5/index.html" target="_blank" rel="noopener noreferrer">Open Pi 5 JavaScript editor</a></article>
<article><h2>MicroDuck Rockchip RK3566</h2><p>Experimental placeholder for offline editing. Add Library includes the MicroDuck Linux bundle with six typed service libraries. Connections are disabled; physical robot behavior is unverified.</p>
<a href="microduck/index.html" target="_blank" rel="noopener noreferrer">Open MicroDuck JavaScript editor</a></article>
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


def build(source, gp_site, output):
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
    profiles = {}
    for profile in ('raspberry-pi5', 'microduck'):
        receipt = package(source, preview / profile, profile=profile)
        profiles[profile] = {'entry': profile + '/index.html', 'target': receipt['target'],
                             'source_commit': receipt['source_commit']}
    (preview / 'index.html').write_text(HUB, encoding='utf-8', newline='\n')
    result = hashes(output)
    if any(result.get(name) != digest for name, digest in original.items()):
        raise ValueError('An existing GP asset changed')
    report = {'schema': 1, 'published': False, 'gp_files_preserved': original,
              'profiles': profiles, 'files': result, 'runtime_upgraded': False,
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
