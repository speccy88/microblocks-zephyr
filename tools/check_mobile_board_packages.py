#!/usr/bin/env python3
"""Verify generated flash bytes and routes, without compiling/flashing firmware."""
# SPDX-License-Identifier: MIT
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from package_pages import fetch
from package_ide import package as rlcd
from package_xrp_ide import package as xrp
from package_fruit_jam_ide import package as fruit_jam
from mobile_editor_source import ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--mobile-source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--fetch',action='store_true')
    args=p.parse_args()
    if args.fetch:fetch(args.source,ROOT)
    summaries=[]
    for name,pack in [('rlcd',rlcd),('xrp',xrp),('fruit-jam',fruit_jam)]:
        reports=[]
        for variant,cache in [('desktop',None),('mobile',args.mobile_source)]:
            output=args.output/name/variant
            pack(args.source.resolve(),output.resolve(),ROOT,cache)
            report=json.loads((output/'assets-report.json').read_text())
            reports.append(report)
            for i,asset in enumerate(report['assets']):
                blob=(output/f'asset-{i}.bin').read_bytes()
                assert len(blob)==asset['flash_bytes']
                assert hashlib.sha256(blob).hexdigest()==asset['flash_sha256']
                raw=gzip.decompress(blob) if asset['encoding']=='gzip' else blob
                assert len(raw)==asset['bytes'] and hashlib.sha256(raw).hexdigest()==asset['sha256']
                if cache:
                    target=args.output/name/'http-root'/asset['path'].lstrip('/')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(raw)
            code=(output/'assets.c').read_text()
            if cache:
                assert ('Fruit Jam.ubl' if name=='fruit-jam' else 'Fruit%20Jam.ubl') in code
                assert '"/mobile/"' in code
                assert '"/index.html"' in code
                assert report['flash_bytes']<7*1024*1024
                assert report['mobile']['added_flash_bytes']<3*1024*1024
        old={a['path']:a['sha256'] for a in reports[0]['assets']}
        new={a['path']:a['sha256'] for a in reports[1]['assets']}
        assert all(new.get(path)==digest for path,digest in old.items() if path!='/microblocks.html')
        summaries.append({'board':name,'desktop_flash_bytes':reports[0]['flash_bytes'],
                          'mobile_total_flash_bytes':reports[1]['flash_bytes'],
                          'added_assets':reports[1]['mobile'],
                          'http_asset_descriptors':reports[1]['files'],
                          'firmware_compiled':False,'flashed':False})
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    print(json.dumps(summaries))


if __name__=='__main__':main()
