#!/usr/bin/env python3
"""Exercise the actual native editor bootstrap scheduling in Node with fake DOM I/O."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path
from fruit_jam_ide_assets import prepare_assets,native_bootstrap
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ide-source',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--node',default='node');a=p.parse_args()
r=Path(__file__).resolve().parents[1];html=native_bootstrap(prepare_assets(r,a.ide_source)['microblocks.html'])
script=re.search(rb'<script id="fruit-jam-native-bootstrap">(.*?)</script>',html,re.S)[1]
fixture=r/'tests/fruit_jam_bootstrap_queue.cjs'
with tempfile.TemporaryDirectory(prefix='fruitjam-bootstrap-',dir=r.parent.resolve()) as folder:
 assert Path(folder).resolve().is_relative_to(r.parent.resolve())
 source=Path(folder)/'bootstrap.cjs';source.write_bytes(script)
 subprocess.run([a.node,'--check',str(source)],check=True,timeout=10)
 result=subprocess.run([a.node,str(fixture),str(source)],check=True,capture_output=True,text=True,timeout=10)
 report=json.loads(result.stdout)
report.update(html_sha256=hashlib.sha256(html).hexdigest(),bootstrap_sha256=hashlib.sha256(script).hexdigest(),fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((r/'tools/fruit_jam_ide_assets.py').read_bytes()).hexdigest())
a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,indent=2))
