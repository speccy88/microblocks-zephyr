"""Read the exact reviewed JS source from Git or a verified local bundle."""
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import stat
import zipfile
from add_js_preview import config, download, safe_name
from js_editor_source import load_manifest, verified_files

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'dependencies/editor-js.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_editor(source):
    source = Path(source)
    manifest = load_manifest(MANIFEST)
    if (source / '.git').exists():
        return verified_files(source, manifest)
    if source.is_symlink() or (source / 'source-manifest.json').read_bytes() != MANIFEST.read_bytes():
        raise ValueError('Exact mobile source manifest required')
    result = {}
    for record in manifest['files']:
        name = record['path']
        path = source / name
        if any(p.is_symlink() for p in [path, *path.parents] if p != source.parent):
            raise ValueError('Symlink in mobile source')
        # The reviewed public preview intentionally omits the raw upstream
        # entry. Retain its exact, hash-checked source template locally.
        raw = (ROOT / 'web/mobile/purejs-source.html').read_bytes() if name == 'purejs.html' and not path.exists() else path.read_bytes()
        if len(raw) != record['bytes'] or sha(raw) != record['sha256']:
            raise ValueError('Mobile source hash mismatch: ' + name)
        result[name] = raw
    return result


def reviewed_archive(path):
    m = config(json.loads((ROOT / 'dependencies/js-preview-site.json').read_text()))
    path = Path(path)
    if path.stat().st_size != m['archive_bytes'] or sha(path.read_bytes()) != m['archive_sha256']:
        raise ValueError('Reviewed JS archive hash/size mismatch')
    with zipfile.ZipFile(path) as z:
        items = z.infolist()
        names = [i.filename for i in items]
        if len(items) != m['file_count'] or len(set(names)) != len(names) or len({n.casefold() for n in names}) != len(names):
            raise ValueError('Reviewed archive file count or duplicates')
        if sum(i.file_size for i in items) > 512 * 1024 * 1024:
            raise ValueError('Reviewed archive expanded bound')
        for item in items:
            if (not safe_name(item.filename) or item.is_dir() or item.flag_bits & 1 or
                    stat.S_IFMT(item.external_attr >> 16) not in (0, stat.S_IFREG) or
                    item.file_size > 32 * 1024 * 1024):
                raise ValueError('Unsafe reviewed archive entry')
        name = 'js-preview/site-manifest.json'
        raw = z.read(name)
        if sha(raw) != m['site_manifest_sha256']:
            raise ValueError('Reviewed site manifest mismatch')
        site = json.loads(raw)
        expected = {**site['files'], name: sha(raw)}
        if set(expected) != set(names):
            raise ValueError('Unlisted reviewed archive file')
        for item in items:
            if sha(z.read(item)) != expected[item.filename]:
                raise ValueError('Reviewed archive file hash mismatch')
    return m


def prepare_archive(path, output, fetch=False, full_site=False):
    """No execution of archived scripts; a new destination is always required."""
    m = config(json.loads((ROOT / 'dependencies/js-preview-site.json').read_text()))
    path, output = Path(path), Path(output)
    if fetch and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        download(m, path)
    reviewed_archive(path)
    output.mkdir(parents=True, exist_ok=False)
    manifest = load_manifest(MANIFEST)
    with zipfile.ZipFile(path) as z:
        if full_site:
            selected = {i.filename: z.read(i) for i in z.infolist()}
        else:
            # The reviewed preview intentionally omits the raw upstream entry.
            # Use the repository template, whose exact pin is checked by read_editor.
            selected = {r['path']: ((ROOT / 'web/mobile/purejs-source.html').read_bytes()
                        if r['path'] == 'purejs.html' and 'js-preview/waveshare/purejs.html' not in z.namelist()
                        else z.read('js-preview/waveshare/' + r['path'])) for r in manifest['files']}
            selected['source-manifest.json'] = MANIFEST.read_bytes()
        for name, raw in selected.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    read_editor(output / 'js-preview/waveshare' if full_site else output)
    return m
