#!/usr/bin/env python3
"""Package the pinned experimental JS editor, without changing GP or SmallVM."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import re
from pathlib import Path
from js_editor_source import load_manifest, verified_files

ROOT = Path(__file__).resolve().parents[1]
REDIRECT = "if (location.protocol === 'http:') { location.protocol = 'https:'; }"
LOCAL_REDIRECT = "if (location.protocol === 'http:' && location.hostname !== '127.0.0.1') { location.protocol = 'https:'; }"
ANCHOR = '\t\t<!-- IDE -->\n\t\t<script type="text/javascript" src="ui/ide.js"></script>'
MICRODUCK_LIBRARIES = ('MicroDuck', 'Head_IMU', 'Depth', 'Gamepad', 'Robot', 'Pad_IMU')
MICRODUCK_BUNDLE = 'Libraries/MicroDuck Linux.ubl'
MICRODUCK_STARTER = 'Libraries/MicroDuck Starter Lab.ubl'
CATALOG = json.loads((ROOT / 'dependencies/editor-targets.json').read_text(encoding='utf-8'))
PROFILES = CATALOG['targets']


def p4_service_files():
    names = ['device-files-core.js', 'device-files-wire.js', 'device-files-controller.js',
             'device-files.js', 'device-files.css', 'p4-neural-core.js', 'p4-neural.css', 'p4-media-core.js',
             'device-sd-core.js', 'device-sd-ui.js']
    result = {name: (ROOT / 'web' / name).read_bytes() for name in names}
    for name in ('p4-services.js', 'p4-neural-client.js', 'p4-media-client.js', 'p4-media.js', 'p4-ui.js'):
        result[name] = (ROOT / 'web/js-editor' / name).read_bytes()
    sources = [{'packaged_path': name, 'source_path': ('web/' if name in names else 'web/js-editor/') + name,
                'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in result.items()]
    result['p4-service-sources.json'] = (json.dumps({'schema': 1, 'sources': sources,
        'gp_sources_modified': False, 'physical_js_acceptance': False,
        'native_owner_checkpoint': 'sealed fe01c3fb v4 source; owner-reported installed image, not hardware checked here',
        'native_owner_pin': 'p4-native-owner.json'}, indent=2) + '\n').encode()
    result['p4-native-owner.json'] = (ROOT / 'dependencies/p4-native-owner.json').read_bytes()
    return result


def readback_catalog(files):
    modules = {}
    for name, raw in sorted(files.items()):
        if not name.startswith(('sources/target/', 'sources/microduck/')) or not name.endswith('.ubl'):
            continue
        declarations = re.findall(r"(?m)^module[ \t]+(?:'((?:[^']|'')*)'|([^\s']+))", raw.decode('utf-8-sig'))
        if len(declarations) != 1:
            raise ValueError('Expected one local module: ' + name)
        quoted, bare = declarations[0]
        module = quoted.replace("''", "'") if quoted else bare
        if module in modules:
            raise ValueError('Ambiguous local module: ' + module)
        modules[module] = {'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return {'schema': 1, 'modules': modules}


def board_files(profile):
    config = PROFILES[profile]
    if not config['libraries']:
        return {}
    vendor = json.loads((ROOT / 'dependencies/gp-board-libraries.json').read_text(encoding='utf-8'))
    vendor_hashes = {entry['path']: entry['sha256'] for entry in vendor['files']}
    bundle, result, sources = b'// Coherent target library import; JS hardware acceptance is pending.\n', {}, []
    for name in config['libraries']:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe target library source')
        raw = (ROOT / path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if name in vendor_hashes and vendor_hashes[name] != digest:
            raise ValueError('Pinned GP library changed: ' + name)
        packaged = 'sources/target/' + path.as_posix()
        result[packaged] = raw
        sources.append({'source_path': name, 'packaged_source': packaged, 'bytes': len(raw),
                        'sha256': digest, 'bundle_offset': len(bundle)})
        bundle += raw + b'\n\n'
    result[config['bundle']] = bundle
    result['target-libraries.json'] = (json.dumps({'schema': 1, 'bundle': config['bundle'],
        'sources': sources, 'gp_source_provenance': vendor, 'hardware_validated': False}, indent=2) + '\n').encode()
    return result


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
    starter, starter_records = bundle, records.copy()
    for name in ('Motion_Simulation', 'Robot_Simulation', 'Simple_Sensors', 'Simple_Practice'):
        source = 'linux/microduck/' + name + '.ubl'
        data = (ROOT / source).read_bytes()
        destination = 'sources/microduck/' + name + '.ubl'
        result[destination] = data
        starter_records.append({'source_path': source, 'packaged_source': destination,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'bundle_offset': len(starter)})
        starter += data + b'\n\n'
    result[MICRODUCK_STARTER] = starter
    result['microduck-starter-libraries.json'] = (json.dumps({'schema': 1, 'bundle': MICRODUCK_STARTER,
        'automatic_import': False, 'physical_hardware_validated': False,
        'action_blocks': 'simulation_only', 'sources': starter_records}, indent=2) + '\n').encode()
    return result


def package(source, output, manifest_path=None, *, profile='development'):
    if profile not in PROFILES:
        raise ValueError('Unknown JavaScript editor target')
    if json.loads((ROOT / 'dependencies/editor-targets.json').read_text(encoding='utf-8')) != CATALOG:
        raise ValueError('Target catalog changed while the builder was running')
    manifest_path = manifest_path or ROOT / 'dependencies/editor-js.json'
    manifest = load_manifest(manifest_path)
    files = verified_files(source, manifest)
    html = files['purejs.html'].decode('utf-8')
    if html.count(REDIRECT) != 1 or html.count(ANCHOR) != 1:
        raise ValueError('Upstream entry point changed; review integration anchors')
    # The original entry point is retained. This generated entry allows only
    # the existing loopback bridge's HTTP origin; remote HTTP still redirects.
    html = html.replace(REDIRECT, LOCAL_REDIRECT).replace(ANCHOR,
        '\t\t<script src="target-config.js"></script>\n'
        '\t\t<script src="target-profile.js"></script>\n'
        '\t\t<script src="linux-compat.js"></script>\n'
        '\t\t<script src="board-transport.js"></script>\n'
        '\t\t<script src="legacy-slots.js"></script>\n'
        '\t\t<script src="legacy-loops.js"></script>\n'
        '\t\t<script src="readback-compat.js"></script>\n'
        '\t\t<script src="readback-library-map.js"></script>\n'
        '\t\t<script src="readback-libraries.js"></script>\n'
        '\t\t<script src="linux-bootstrap.js"></script>\n' + ANCHOR)
    if profile == 'esp32p4':
        tags = ['<link rel="stylesheet" href="device-files.css">', '<link rel="stylesheet" href="p4-neural.css">']
        for name in ('device-files-core.js', 'device-files-wire.js', 'device-files-controller.js', 'device-sd-core.js', 'device-sd-ui.js', 'device-files.js',
                     'p4-neural-core.js', 'p4-neural-client.js', 'p4-services.js', 'p4-media-core.js',
                     'p4-media-client.js', 'p4-media.js', 'p4-ui.js'):
            tags.append('<script src="' + name + '"></script>')
        html = html.replace('\t\t<script src="linux-bootstrap.js"></script>',
                            '\n'.join(tags) + '\n\t\t<script src="linux-bootstrap.js"></script>')
        services = p4_service_files()
        if files.keys() & services.keys():
            raise ValueError('P4 service path collides with upstream')
        files.update(services)
    files['index.html'] = html.encode('utf-8')
    # The existing Linux bridge intentionally serves this fixed entry name.
    files['microblocks.html'] = files['index.html']
    # Explicit targets have no executable unprofiled alternative entry point.
    if profile != 'development':
        files['sources/upstream-entry/purejs.html.txt'] = files.pop('purejs.html')
    files['linux-compat.js'] = (ROOT / 'web/js-editor/linux-compat.js').read_bytes()
    files['board-transport.js'] = (ROOT / 'web/js-editor/board-transport.js').read_bytes()
    files['target-profile.js'] = (ROOT / 'web/js-editor/target-profile.js').read_bytes()
    target = {**PROFILES[profile], 'id': profile,
              'requires_robot_services': profile == 'microduck', 'physical_microduck_validated': False,
              'hosted_wss_commissioned': False}
    # GP library names may be quoted, including spaces (e.g. distance (cm)).
    # Record both forms so a missing dependency cannot compile to a dummy zero.
    target['function_names'] = sorted({(quoted.replace("''", "'") if quoted else bare)
        for source_name in PROFILES[profile]['libraries']
        for quoted, bare in re.findall(r"^[ \t]*to[ \t]+(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_]*))(?=\s|$)",
            (ROOT / source_name).read_text(encoding='utf-8'), re.MULTILINE)})
    files['target-profile.json'] = (json.dumps(target, indent=2) + '\n').encode()
    catalog = {name: {**value, 'id': name} for name, value in PROFILES.items()}
    files['target-config.js'] = ('// Generated local profile; upstream files remain unchanged.\n'
        'const MicroBlocksJSTargets = ' + json.dumps(catalog, separators=(',', ':')) + ';\n'
        'const MicroBlocksJSProfile = Object.freeze(' + json.dumps(target, separators=(',', ':')) + ');\n').encode()
    files['editor-targets.json'] = (ROOT / 'dependencies/editor-targets.json').read_bytes()
    files['legacy-slots.js'] = (ROOT / 'web/js-editor/legacy-slots.js').read_bytes()
    files['legacy-loops.js'] = (ROOT / 'web/js-editor/legacy-loops.js').read_bytes()
    files['readback-compat.js'] = (ROOT / 'web/js-editor/readback-compat.js').read_bytes()
    files['readback-libraries.js'] = (ROOT / 'web/js-editor/readback-libraries.js').read_bytes()
    files['linux-bootstrap.js'] = (ROOT / 'web/js-editor/bootstrap.js').read_bytes()
    files['licenses/LOCAL-MIT.txt'] = (ROOT / 'LICENSE').read_bytes()
    files['THIRD_PARTY_NOTICES.md'] = (ROOT / 'web/js-editor/THIRD_PARTY_NOTICES.md').read_bytes()
    files['source-manifest.json'] = manifest_path.read_bytes()
    files['matrix-source.json'] = (ROOT / 'dependencies/unoq-matrix-gp.json').read_bytes()
    local = microduck_files() if profile in ('development', 'microduck') else board_files(profile)
    if files.keys() & local.keys():
        raise ValueError('Local library path collides with upstream')
    files.update(local)
    catalog = readback_catalog(files)
    files['readback-libraries.json'] = (json.dumps(catalog, indent=2) + '\n').encode()
    files['readback-library-map.js'] = ('// Generated pinned local library readback catalog.\nconst MicroBlocksReadbackLibraryMap = ' + json.dumps(catalog) + ';\n').encode()
    # Official MB_Files and its picker require the build-generated file index.
    # Generate it from actual packaged paths; no upstream engine patch needed.
    if 'files.txt' in files:
        raise ValueError('Upstream now provides files.txt; review index generation')
    files['files.txt'] = ('\n'.join(sorted(files)) + '\n').encode()
    receipt = {'schema': 1, 'profile': profile, 'target': target,
               'source_commit': manifest['source_commit'], 'runtime_upgraded': False,
               'upstream_engine_modified': False, 'graphical_acceptance': False,
               'upstream_entry_relocated_as_text': profile != 'development',
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
    parser.add_argument('--profile', choices=PROFILES, default='development')
    args = parser.parse_args()
    result = package(args.source, args.output, profile=args.profile)
    print(f"Packaged {len(result['files'])} files from {result['source_commit']}")
