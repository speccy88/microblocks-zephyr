"""Validate authored block documentation and build offline, shared help assets."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
import re
from pathlib import Path
from p2_library_groups import group_for

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('boards', 'integration', 'libraries', 'linux', 'bilingual-kws')


def inventory():
    """Discover public/advanced specs, never private implementation functions."""
    result = {}
    for directory in SOURCE_DIRS:
        for path in sorted((ROOT / directory).rglob('*.ubl')):
            text = path.read_text(encoding='utf-8')
            module = re.search(r"^module\s+'([^']+)'", text, re.M)
            matches = list(re.finditer(r"^\s*spec[ \t]+'([^']*)'[ \t]+'([^']+)'[ \t]+'([^']*)'", text, re.M))
            if len(matches) != len(re.findall(r'^\s*spec[ \t]+', text, re.M)):
                raise ValueError(f'Review unsupported block spec syntax in {path}')
            for match in matches:
                kind, selector, label = match.groups()
                entry = result.setdefault(selector, {'selector': selector, 'label': label,
                    'kind': kind, 'sources': [], 'modules': []})
                source = path.relative_to(ROOT).as_posix()
                if source not in entry['sources']: entry['sources'].append(source)
                name = module.group(1) if module else path.stem
                if source == 'boards/propeller2/integration/P2_Hardware.ubl':
                    name = group_for(selector)
                if name not in entry['modules']: entry['modules'].append(name)
    source = 'web/js-editor/sfc-editor.js'
    text = (ROOT / source).read_text(encoding='utf-8').split('const specs=[', 1)[1].split('];', 1)[0]
    for kind, selector, label in re.findall(r"\['([^']*)','([^']+)','([^']*)'", text):
        result[selector] = {'selector': selector, 'label': label, 'kind': kind,
                            'sources': [source], 'modules': ['Steps and Transitions']}
    return dict(sorted(result.items()))


def catalog(content_dir=None):
    expected, authored = inventory(), {}
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError(f'Duplicate JSON key in block help: {key}')
            result[key] = value
        return result
    for path in sorted((content_dir or ROOT / 'docs/block-help').glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
        if document.get('schema') != 1 or not isinstance(document.get('blocks'), dict):
            raise ValueError(f'{path}: expected schema 1 and blocks object')
        for selector, entry in document['blocks'].items():
            if selector in authored: raise ValueError(f'Duplicate block help: {selector}')
            if not isinstance(entry, dict): raise ValueError(f'Invalid block help: {selector}')
            for field in ('summary', 'returns'):
                if not isinstance(entry.get(field), str) or not entry[field].strip():
                    raise ValueError(f'{selector}: missing {field}')
            for field in ('inputs', 'prerequisites', 'notes'):
                values = entry.get(field)
                if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                    raise ValueError(f'{selector}: invalid {field}')
            if not entry['prerequisites']: raise ValueError(f'{selector}: missing prerequisites')
            examples = entry.get('examples')
            if not isinstance(examples, list) or not examples: raise ValueError(f'{selector}: missing examples')
            for example in examples:
                if not isinstance(example, dict) or any(not isinstance(example.get(f), str) or not example[f].strip() for f in ('title', 'code', 'explanation')):
                    raise ValueError(f'{selector}: incomplete example')
            authored[selector] = entry
    missing, unknown = expected.keys() - authored.keys(), authored.keys() - expected.keys()
    if missing or unknown:
        raise ValueError('Block help coverage: missing=' + ', '.join(sorted(missing)) + '; unknown=' + ', '.join(sorted(unknown)))
    return {selector: {**authored[selector], **metadata} for selector, metadata in expected.items()}


def assets():
    blocks = catalog()
    data = json.dumps({'schema': 1, 'blocks': blocks}, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    index = json.dumps(list(blocks), ensure_ascii=True, separators=(',', ':'))
    result = {'block-help-data.js': ('globalThis.MicroBlocksBlockHelpData = ' + data + ';\n').encode(),
              'block-help-index.js': ('globalThis.MicroBlocksBlockHelpIndex = ' + index + ';\n').encode()}
    for name in ('block-help.js', 'block-help.html', 'block-help-page.js', 'block-help.css'):
        result[name] = (ROOT / 'web/js-editor' / name).read_bytes()
    page = result['block-help.html'].decode()
    for name in ('block-help-data.js', 'block-help-page.js', 'block-help.css'):
        page = page.replace('"' + name + '"', '"' + name + '?v=' + hashlib.sha256(result[name]).hexdigest()[:16] + '"')
    result['block-help.html'] = page.encode()
    version = hashlib.sha256(result['block-help.html']).hexdigest()[:16]
    result['block-help-index.js'] += ('globalThis.MicroBlocksBlockHelpVersion = "' + version + '";\n').encode()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', action='store_true')
    args = parser.parse_args()
    if args.inventory: print(json.dumps(inventory(), indent=2))
    else: print(f'Validated help for {len(catalog())} custom block selectors')
