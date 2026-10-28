#!/usr/bin/env python3
"""Build an offline Pi5 installer candidate. Never download, execute or publish."""
# SPDX-License-Identifier: MIT
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import tarfile

from package_js_editor import package as editor_package

ROOT=Path(__file__).resolve().parents[1]

BOOTSTRAP=r'''#!/bin/sh
set -eu
umask 077
command -v python3 >/dev/null || { echo 'Python3 is required' >&2; exit 1; }
command -v curl >/dev/null || { echo 'curl is required' >&2; exit 1; }
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
curl --fail --location --proto '=https' --tlsv1.2 --max-filesize 67108864 '__URL__' -o "$work/bundle.tar.gz"
printf '%s  %s\n' '__SHA__' "$work/bundle.tar.gz" | sha256sum --check --status -
python3 - "$work/bundle.tar.gz" "$work/content" <<'PY'
import pathlib,sys,tarfile
archive,destination=map(pathlib.Path,sys.argv[1:]);destination.mkdir(mode=0o700)
with tarfile.open(archive,'r:gz') as bundle:
 members=bundle.getmembers();names=[m.name for m in members]
 if len(members)>5000 or len(names)!=len(set(names)) or sum(m.size for m in members)>268435456:raise SystemExit('Invalid bundle bounds')
 for m in members:
  p=pathlib.PurePosixPath(m.name)
  if not m.isfile() or m.size>67108864 or p.is_absolute() or '..' in p.parts or '\\' in m.name or p.as_posix()!=m.name:raise SystemExit('Unsafe bundle member')
  target=destination/m.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(bundle.extractfile(m).read())
PY
python3 -B "$work/content/linux/arm64/install_bundle.py" "$@"
'''


def archive_bytes(entries):
    output=io.BytesIO()
    with gzip.GzipFile(fileobj=output,mode='wb',filename='',mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode='w',format=tarfile.USTAR_FORMAT) as tar:
            for name,data in sorted(entries.items()):
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o644;member.mtime=0;tar.addfile(member,io.BytesIO(data))
    return output.getvalue()


def package(binary,expected_binary_sha,prepared,upstream,wheel,output,version):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',version) or version=='latest':raise ValueError('Pinned version required')
    if output.exists():raise FileExistsError('Refusing existing output')
    raw=binary.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_binary_sha:raise ValueError('Binary differs from verified Pi output')
    lock=json.loads((ROOT/'dependencies/linux-bridge.json').read_text())
    if wheel.name!=lock['filename'] or len(wheel.read_bytes())!=lock['bytes'] or hashlib.sha256(wheel.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('Pinned wheel differs')
    source=json.loads((prepared/'source-manifest.json').read_text())
    if source['source_commit']!='2071df569623ba9cdcd6f8106b61796e047df38b' or source['sanitize']:raise ValueError('Ordinary pinned prepared source required')
    source_entries={}
    for name,record in source['sources'].items():
        data=(prepared/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=record['prepared_sha256']:raise ValueError('Prepared source mismatch: '+name)
        source_entries[name]=data
    for name in ('build.sh','LICENSE','source-manifest.json'):source_entries[name]=(prepared/name).read_bytes()
    source_archive=archive_bytes(source_entries)
    output.mkdir(parents=True);content=output/'content';content.mkdir()
    spec=importlib.util.spec_from_file_location('pi_binary_package',ROOT/'linux/arm64/package.py');native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    native.package(raw,(prepared/'LICENSE').read_bytes(),content/'binary.tar.gz',version)
    (content/'binary.tar.gz.sha256').unlink() # Binary digest is authenticated by the bundle manifest.
    (content/'corresponding-source.tar.gz').write_bytes(source_archive)
    editor=editor_package(upstream,content/'editor',profile='raspberry-pi5')
    for name in ('linux/arm64/install_bundle.py','linux/arm64/service.py','linux/arm64/session.py','linux/arm64/bridge.py',
                 'scripts/install-smallvm-linux-arm64.sh','scripts/uninstall-smallvm-linux-arm64.sh','dependencies/linux-bridge.json'):
        target=content/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    (content/'wheels').mkdir();shutil.copyfile(wheel,content/'wheels'/wheel.name)
    for name in ('LICENSE','LICENSES.md'):
        shutil.copyfile(ROOT/name,content/name)
    shutil.copyfile(ROOT/'docs/PI_INSTALLER.md',content/'README.md')
    entries={p.relative_to(content).as_posix():p.read_bytes() for p in content.rglob('*') if p.is_file()}
    editor_files={name:hashlib.sha256(data).hexdigest() for name,data in entries.items() if name.startswith('editor/')}
    manifest={'schema':1,'platform':'raspberry-pi5-aarch64','version':version,'status':'unpublished experimental candidate',
              'binary':{'version':version,'sha256':hashlib.sha256(entries['binary.tar.gz']).hexdigest(),'executable_sha256':expected_binary_sha},
              'source_commit':source['source_commit'],'source_archive_sha256':hashlib.sha256(source_archive).hexdigest(),
              'editor_sha256':hashlib.sha256(json.dumps(editor_files,sort_keys=True).encode()).hexdigest(),
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in entries.items()}}
    manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode();entries['bundle-manifest.json']=manifest_bytes;(content/'bundle-manifest.json').write_bytes(manifest_bytes)
    archive=output/f'smallvm-pi5-{version}.tar.gz';archive.write_bytes(archive_bytes(entries));digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    url=f'https://github.com/speccy88/microblocks-zephyr/releases/download/{version}/'+archive.name
    script=output/'install-pi5.sh';script.write_text(BOOTSTRAP.replace('__URL__',url).replace('__SHA__',digest),encoding='utf-8',newline='\n')
    script_sha=hashlib.sha256(script.read_bytes()).hexdigest();script_url=url.rsplit('/',1)[0]+'/install-pi5.sh'
    report={'version':version,'archive':archive.name,'archive_bytes':archive.stat().st_size,'archive_sha256':digest,'bootstrap_sha256':script_sha,
            'files':len(entries),'source_archive_sha256':manifest['source_archive_sha256'],'executable_sha256':expected_binary_sha,
            'published':False,'hardware_acceptance':'pending fresh-prefix installation/reboot; packaging does not establish acceptance',
            'planned_public_command':f'mb_installer=$(mktemp) && curl --fail --location --proto =https --tlsv1.2 {script_url} -o "$mb_installer" && printf \'%s  %s\\n\' {script_sha} "$mb_installer" | sha256sum --check --status - && bash "$mb_installer"',
            'prerequisites':['64-bit Raspberry Pi5 Linux','Python3.10+ and python3-venv','curl, bash, coreutils, systemd user manager','Boot lingering already enabled or explicit interactive consent']}
    (output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','prepared','upstream','wheel','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--binary-sha256',required=True);p.add_argument('--version',required=True);a=p.parse_args()
    print(json.dumps(package(a.binary,a.binary_sha256,a.prepared,a.upstream,a.wheel,a.output,a.version)))
