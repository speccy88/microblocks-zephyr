"""Package reviewed native P2 images and the browser loader; never flash."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def assets(firmware):
    pin=json.loads((ROOT/'dependencies/p2-web-installer.json').read_text(encoding='utf-8'))
    files={name:(ROOT/'web/p2-installer'/name).read_bytes() for name in ['index.html','installer.js','loader.js','installer.css']}
    header=(ROOT/'third_party/loadp2/flash_loader.h').read_text(encoding='utf-8')
    values=re.search(r'flash_loader_bin\[\]\s*=\s*\{(.*?)\}',header,re.S)
    stub=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',values[1]))
    if len(stub)!=496:raise ValueError('Review changed P2 flash programmer')
    files['flash-loader.bin']=stub
    files['LICENSE-loadp2.txt']=(ROOT/'third_party/loadp2/LICENSE').read_bytes()
    acceptance=json.loads((ROOT/'boards/propeller2/hardware.json').read_text(encoding='utf-8'))['web_installer']
    manifest={'schema':1,'vm_version':pin['vm_version'],'extension_revision':pin['extension_revision'],
        'compiler_commit':pin['compiler_commit'],'flexprop_release':pin['flexprop_release'],
        'loadp2_commit':pin['loadp2_commit'],'images':{},
        'flasher':{'bytes':len(stub),'sha256':hashlib.sha256(stub).hexdigest()},
        'ram_runtime_can_initialize_flash':True,'project_storage_flash_offsets':[2097152,8388608],
        'physical_target':'edge32','actual_browser_usb_transfer_verified':acceptance.get('actual_browser_usb_transfer_verified') is True,
        'browser_hardware_evidence':acceptance.get('browser_hardware_evidence')}
    for board,expected in pin['expected_images'].items():
        name='vm_propeller2_'+board+'.bin';raw=(Path(firmware)/name).read_bytes()
        if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:
            raise ValueError('Refuse unreviewed P2 firmware: '+board)
        files[name]=raw;manifest['images'][board]={**expected,'file':name}
    manifest['source_commit']=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    manifest['native_sources_sha256']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT/'boards/propeller2/native').rglob('*')) if p.is_file() and p.suffix in {'.c','.h'}}
    files['firmware.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    # Request the matching UI code when Pages caches a prior release.
    html=files['index.html'].decode()
    for name in ['loader.js','installer.js','installer.css']:
        version=hashlib.sha256(files[name]).hexdigest()[:16]
        html=html.replace('="'+name+'"','="'+name+'?v='+version+'"')
    files['index.html']=html.encode()
    return files


def add(site,firmware):
    folder=Path(site)/'install/propeller2'
    if folder.exists():raise ValueError('Fresh P2 installer output required')
    files=assets(firmware)
    folder.mkdir(parents=True)
    for name,raw in files.items():(folder/name).write_bytes(raw)
    receipt={'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()},
        'vm_version':405,'extension_revision':8,'firmware_built_from_source':True,
        'hardware_install_performed_by_packager':False}
    (folder/'build-manifest.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'files':len(files),'images':3,'hardware_install_performed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',type=Path,required=True);p.add_argument('--firmware',type=Path,required=True)
    a=p.parse_args();print(json.dumps(add(a.site,a.firmware)))
