#!/usr/bin/env python3
"""Build the open same-origin Pi touch editor; never start a listener or VM."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
from package_mobile_editor import mobile_files, ROOT


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Review changed Pi mobile source anchor: ' + old[:70])
    return text.replace(old, new)


def package(source, output):
    output = Path(output)
    if output.exists():
        raise ValueError('A fresh package output is required')
    files, original = mobile_files(source, runtime='board', board='waveshare', desktop='/')
    browser = files['mobile-browser.js'].decode('utf-8')
    browser = replace_once(browser, "const supported = ['rlcd', 'fruit-jam', 'xrp'];", "const supported = ['pi5'];")
    browser = replace_once(browser,
        "const local = location.protocol === 'http:' && (privateIP(location.hostname) || ['127.0.0.1', 'localhost'].includes(location.hostname));",
        "const local = location.protocol === 'http:' && (privateIP(location.hostname) || location.hostname === '127.0.0.1') && profile.local_pi === 'open-http-v1';")
    browser = replace_once(browser,
        "Connect uses this board\u2019s same-origin /ws/vm. Compatible Wi-Fi firmware is required. A socket alone does not confirm the VM is ready.",
        'Connect directly to the Pi over the local network or configured Tailscale site. Keep this page in the foreground while programming.')
    files['mobile-browser.js'] = browser.encode('utf-8')
    files['iphone-bootstrap.js'] = replace_once(files['iphone-bootstrap.js'].decode('utf-8'),
        'Join the same network as your board. Its MicroBlocks Wi-Fi firmware must already be installed.',
        'Join the same network as your Raspberry Pi. Its SmallVM session must already be running.').encode('utf-8')
    files['pi-compiler.js'] = (ROOT / 'web/js-editor/pi-compiler.js').read_bytes()
    for name in ('pi-updates.js', 'pi-updates.css'):
        files[name] = (ROOT / 'web/js-editor' / name).read_bytes()
    html = files['index.html'].decode('utf-8')
    html = replace_once(html, '</head>', '<link rel="stylesheet" data-mobile-href="pi-updates.css">\n</head>')
    match = re.search(r'(<script id="mobile-load-config" type="application/json">)(.*?)(</script>)', html)
    if match is None:
        raise ValueError('Exact mobile load configuration required')
    config = json.loads(match[2])
    config['profile'].update(board='pi5', local_pi='open-http-v1')
    index = next(i for i, item in enumerate(config['scripts']) if item.get('src') == 'mobile-browser.js')
    config['scripts'].insert(index, {'src': 'pi-compiler.js'})
    config['scripts'].insert(index + 2, {'src': 'pi-updates.js'})
    html = html[:match.start(2)] + json.dumps(config, separators=(',', ':')).replace('<', '\\u003c') + html[match.end(2):]
    files['index.html'] = files['microblocks.html'] = html.encode('utf-8')
    files['iphone-boards.json'] = json.dumps({'schema': 1, 'physical_iphone_validated': False, 'boards': [
        {'id': 'pi5', 'name': 'Raspberry Pi 5', 'transport': 'wifi',
         'note': 'Program the Pi through this local session. GPIO and MicroDuck hardware control are unavailable.'}
    ]}).encode('utf-8')
    del files['build-manifest.json']
    del files['files.txt']
    packaged = {'mobile/' + name: raw for name, raw in files.items()}
    packaged['microblocks.html'] = html.encode('utf-8')
    packaged['mobile/files.txt'] = ('\n'.join(sorted(files)) + '\n').encode('utf-8')
    receipt = {'schema': 1, 'profile': 'pi-open-lan', 'authentication': False, 'encryption': False,
        'source_commit': original['source_commit'], 'upstream_engine_modified': False,
        'physical_iphone_validated': False,
        'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(packaged.items())}}
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in packaged.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (output / 'pi-build-manifest.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return {'output': str(output), 'files': len(packaged), 'listener_started': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(package(a.source, a.output), indent=2))
