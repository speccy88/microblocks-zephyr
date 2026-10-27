#!/usr/bin/env python3
"""Build one real pinned GP editor for an explicit loopback Linux bridge.

Default root: build-artifacts/linux-editor; bridge port: 8876. The builder does
not start a server, connect to a VM or publish anything. Source hashes are
checked before any output is changed. Published Pages keeps its separate CSP.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

from fruit_jam_ide_assets import prepare_assets
from linux_editor_assets import linux_package, replace_once

PROFILES = {'raspberry-pi5': 'Raspberry Pi 5 — Linux ARM64', 'microduck': 'MicroDuck — Linux ARM64 (hardware unvalidated)'}
MARKER = 'microblocks-linux-editor-v1\n'


class AssetReferences(HTMLParser):
    def __init__(self):
        super().__init__(); self.paths = []
    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag in ('script', 'img') and values.get('src'):
            self.paths.append(values['src'])
        if tag == 'link' and values.get('href'):
            self.paths.append(values['href'])


def verified_assets(source, repo):
    manifest = json.loads((repo / 'dependencies/ide-assets.json').read_text(encoding='utf-8'))
    originals = {}
    for item in manifest['files']:
        name = Path(item['path'])
        if name.is_absolute() or '..' in name.parts or name.as_posix() in originals:
            raise ValueError('Unsafe or duplicate IDE source path')
        path = source / name
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise ValueError('IDE source link escapes its root: ' + str(name))
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256'] or len(raw) != item['bytes']:
            raise ValueError('IDE source changed: ' + str(name))
        originals[name.as_posix()] = raw
    return manifest, originals


def local_html(html, assets, profile, port):
    if profile not in PROFILES or isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError('Use a known Linux profile and an unprivileged bridge port')
    text = html.decode('utf-8')
    locator = 'Module.locateFile=function(name,prefix){return prefix+name+"?v=26eb855451371f4c";};'
    text = replace_once(text, locator, 'Module.locateFile=function(name,prefix){return prefix+name;};')

    def remove_cachebuster(match):
        attribute, value = match.groups()
        parts = urlsplit(value)
        if parts.scheme or parts.netloc or not parts.query:
            return match[0]
        if re.fullmatch(r'v=[a-fA-F0-9]{8,64}', parts.query) and not parts.fragment and parts.path in assets:
            return attribute + '="' + parts.path + '"'
        raise ValueError('Unknown local editor URL query; refusing a broad rewrite: ' + value)
    text = re.sub(r'\b(src|href)="([^"]+)"', remove_cachebuster, text)
    config = json.dumps({'board': profile, 'name': PROFILES[profile], 'runtime': 'linux',
                         'connection_enabled': True, 'local_bridge': True}, separators=(',', ':'), ensure_ascii=True)
    tag = '<script src="unoq-network.js"></script>'
    text = replace_once(text, tag,
        '<link rel="stylesheet" href="portal.css">\n'
        '<script>window.PORTAL_BOARD=' + config + ';</script>\n'
        '<script src="portal-core.js"></script>\n'
        '<script src="unoq-network.js"></script>')
    policy = ("default-src 'self' data: blob:; connect-src 'self' ws://127.0.0.1:" + str(port) +
              ' ws://localhost:' + str(port) + "; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
              "style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'")
    text = replace_once(text, '<meta charset="utf-8">', '<meta charset="utf-8">\n'
        '<meta name="referrer" content="no-referrer">\n'
        '<meta http-equiv="Content-Security-Policy" content="' + policy + '">')
    references = AssetReferences(); references.feed(text)
    for url in references.paths:
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or parts.query or parts.fragment or parts.path not in assets or '..' in Path(parts.path).parts:
            raise ValueError('Dedicated editor boot resource is not an exact local asset: ' + url)
    return text.encode('utf-8')


def build(source, output, repo, profile='raspberry-pi5', port=8876):
    if output.is_symlink():
        raise ValueError('Output must not be a symlink')
    source, output, repo = source.resolve(), output.resolve(), repo.resolve()
    if source == output or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('IDE source and build output must be disjoint')
    manifest, originals = verified_assets(source, repo)
    js, data = linux_package(originals['gp_wasm.js'], originals['gp_wasm.data'])
    common = prepare_assets(repo, source)
    assets = dict(originals)
    assets.update({name: common[name] for name in ('microblocks.html', 'gettext.js')})
    gate = b"""Module.preRun.push(function() {
 addRunDependency('board-english');
 Promise.resolve(GetText.ready).then(function(){removeRunDependency('board-english');},
 function(){Module.setStatus('Cannot load local language assets. Reload to retry.');});
});
"""
    assets.update({'gp_wasm.js': gate + js, 'gp_wasm.data': data,
                   'portal-core.js': (repo / 'web/portal/portal-core.js').read_bytes(),
                   'portal.css': (repo / 'web/portal/portal.css').read_bytes(),
                   'unoq-network.js': (repo / 'web/portal/portal-adapter.js').read_bytes()})
    assets['microblocks.html'] = local_html(assets['microblocks.html'], assets, profile, port)
    assets['index.html'] = assets['microblocks.html']
    if output.exists() and any(output.iterdir()):
        marker = output / '.linux-editor-build'
        if not marker.is_file() or marker.is_symlink() or marker.read_text(encoding='utf-8') != MARKER:
            raise ValueError('Output is not an owned Linux editor build')
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in assets.items():
        target = output / name
        if target.is_symlink() or not target.resolve().is_relative_to(output):
            raise ValueError('Output asset escapes build root: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    (output / '.linux-editor-build').write_text(MARKER, encoding='utf-8', newline='\n')
    for name in ('LICENSE', 'LICENSES.md'):
        shutil.copyfile(repo / name, output / name)
    shutil.copytree(repo / 'licenses', output / 'licenses', dirs_exist_ok=True)
    (output / 'UPSTREAM.md').write_text('Real MicroBlocks GP 2.5.8 editor; MPL-2.0.\n'
        'Corresponding GP sources remain embedded in gp_wasm.data.\n'
        f"Pinned source: {manifest['source_repository']}/tree/{manifest['source_commit']}\n"
        'Linux Core adds no GPIO, robot, sensor or media hardware primitives.\n'
        'This package is for the explicit loopback HTTP/WS bridge, not a Pages TLS fallback.\n', encoding='utf-8', newline='\n')
    report = {'real_editor': 'MicroBlocks GP 2.5.8', 'profile': profile, 'runtime': 'linux',
              'source_commit': manifest['source_commit'], 'loopback_bridge_port': port,
              'source_manifest_sha256': hashlib.sha256((repo / 'dependencies/ide-assets.json').read_bytes()).hexdigest(),
              'hardware_library': 'Linux Core; no added hardware primitives',
              'project_api': ['portal.serialize', 'portal.load'], 'boot_assets_local': True,
              'physical_browser_acceptance': False,
              'files': {name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in sorted(assets.items())}}
    (output / 'build-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide-source', type=Path, default=Path('build-artifacts/ide-source'))
    parser.add_argument('--output', type=Path, default=Path('build-artifacts/linux-editor'))
    parser.add_argument('--profile', choices=tuple(PROFILES), default='raspberry-pi5')
    parser.add_argument('--port', type=int, default=8876)
    args = parser.parse_args()
    report = build(args.ide_source, args.output, Path(__file__).resolve().parents[1], args.profile, args.port)
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}, indent=2))
