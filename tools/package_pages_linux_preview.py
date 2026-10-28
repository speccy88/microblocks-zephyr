#!/usr/bin/env python3
"""Compose an unpublished Linux target preview with a stable five-board portal.

Build each input with its own immutable source's package_pages.py first. This
tool never downloads, checks out branches, deploys, or changes either input.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

STABLE = {'fruit-jam', 'waveshare', 'esp32p4', 'propeller2', 'xrp-rp2350'}
LINUX = {'raspberry-pi5', 'microduck'}


def files(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are not accepted in a static build')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def build(stable, linux, output, stable_commit, linux_commit):
    stable, linux, output = map(lambda p: Path(p).resolve(), (stable, linux, output))
    for commit in (stable_commit, linux_commit):
        if not re.fullmatch('[0-9a-f]{40}', commit):
            raise ValueError('Record exact immutable source commit IDs')
    if any(output == p or output in p.parents or p in output.parents for p in (stable, linux)):
        raise ValueError('Inputs and output must be separate trees')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be empty')
    stable_manifest = json.loads((stable / 'build-manifest.json').read_text())
    linux_manifest = json.loads((linux / 'build-manifest.json').read_text())
    if set(stable_manifest['boards']) != STABLE or not LINUX <= set(linux_manifest['boards']):
        raise ValueError('Expected a stable five-board build and two Linux profiles')
    if linux_manifest['boards']['microduck']['hardware_connection_enabled'] is not False:
        raise ValueError('MicroDuck preview must remain disconnected')
    before, preview_hashes = files(stable), files(linux)
    html = (stable / 'index.html').read_text(encoding='utf-8')
    script = (stable / 'portal.js').read_text(encoding='utf-8')
    if html.count('</select>') != 1 or 'value="raspberry-pi5"' in html:
        raise ValueError('Stable board selector changed; review before composing')
    route = "const path='editor/'+selected+'/microblocks.html';"
    status = "status.textContent=selected==='esp32p4'?"
    if script.count(route) != 1 or script.count(status) != 1:
        raise ValueError('Stable routing changed; review before composing')
    html = html.replace('</select>', '<option value="raspberry-pi5">Raspberry Pi 5 (Linux preview)</option>'
                        '<option value="microduck">MicroDuck Rockchip RK3566 (experimental placeholder)</option></select>')
    script = script.replace(route, "const path=(selected==='raspberry-pi5'||selected==='microduck'?'preview/':'')+'editor/'+selected+'/microblocks.html';")
    script = script.replace(status, "status.textContent=selected==='raspberry-pi5'?"
                            "'Raspberry Pi 5: standalone Linux preview. No robot services required. Use a trusted WSS bridge here, or the Pi editor through a local SSH tunnel. No released installer is advertised.':"
                            "selected==='microduck'?'MicroDuck Rockchip RK3566: experimental placeholder. Offline editing only; physical hardware, services and installation remain unverified.':selected==='esp32p4'?")
    # Preserve all stable assets, including its five complete editor directories.
    shutil.copytree(stable, output, dirs_exist_ok=True)
    preview = output / 'preview'
    for board in sorted(LINUX):
        shutil.copytree(linux / 'editor' / board, preview / 'editor' / board)
    for name in ('portal.css', 'portal-core.js', 'LICENSE', 'LICENSES.md', 'UPSTREAM.md'):
        shutil.copyfile(linux / name, preview / name)
    shutil.copytree(linux / 'licenses', preview / 'licenses')
    (output / 'index.html').write_text(html, encoding='utf-8', newline='\n')
    (output / 'portal.js').write_text(script, encoding='utf-8', newline='\n')
    # Bust the existing script cache after the route additions.
    version = hashlib.sha256(script.encode()).hexdigest()[:16]
    html = re.sub(r'src="portal\.js(?:\?v=[^"]*)?"', 'src="portal.js?v=' + version + '"', html)
    (output / 'index.html').write_text(html, encoding='utf-8', newline='\n')
    after = files(output)
    preserved = {name: digest for name, digest in before.items() if name not in ('index.html', 'portal.js')}
    if any(after.get(name) != digest for name, digest in preserved.items()):
        raise ValueError('A stable asset changed unexpectedly')
    report = {'stable_source_commit': stable_commit, 'linux_source_commit': linux_commit,
              'stable_input': before, 'linux_input': preview_hashes,
              'preserved_stable_files': len(preserved), 'stable_editor_profiles': sorted(STABLE),
              'added_preview_profiles': sorted(LINUX), 'public_deployment_performed': False,
              'outputs': after}
    (output / 'linux-preview-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stable', 'linux', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('stable-commit', 'linux-commit'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = build(args.stable, args.linux, args.output, args.stable_commit, args.linux_commit)
    print(json.dumps({k: v for k, v in result.items() if k not in ('stable_input', 'linux_input', 'outputs')}, indent=2))
