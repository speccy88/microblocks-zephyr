#!/usr/bin/env python3
"""Real GP parsing, compilation, save/reload, native specs and SVG lookup checks."""
# SPDX-License-Identifier: MPL-2.0
import argparse,json,shutil,subprocess,sys
from pathlib import Path

def run(editor,output,repo,node):
 if output.exists():raise ValueError('Choose a new compiler evidence directory')
 output.mkdir(parents=True)
 records=[]
 def compile(name,source,checks=None,expected='PASS'):
  dest=output/(name+'.json');cmd=[node,str(repo/'tools/sfc_gp_compile.cjs'),str(editor),str(source),str(dest)]
  if checks:cmd.append(str(checks))
  result=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
  if not dest.exists():raise RuntimeError(result.stderr or result.stdout or 'GP compiler produced no report')
  report=json.loads(dest.read_text());assert report['status']==expected,(name,report.get('error'),report.get('messages'))
  record={'case':name,'expected':expected,'actual':report['status']}
  if 'result' in report:record.update(chunks=len(report['result']['chunks']),headless_checks=len(report['result'].get('headless_checks',[])))
  records.append(record)
 fixtures=repo/'tests/fixtures/sfc_native'
 for fixture in sorted(fixtures.glob('*.ubp')):compile(fixture.stem,fixture,expected='FAIL' if fixture.stem.startswith('invalid-') else 'PASS')
 compile('native-specs-and-live-state',fixtures/'or-3.ubp',repo/'tests/sfc_all_headless.gp')
 compile('named-svg-software-render',fixtures/'or-3.ubp',repo/'tests/sfc_svg_resources.gp')
 assert len(records)==33
 summary={'status':'PASS','records':records,'compiler':'genuine pinned GP 2.5.8','hardware_access':False,
  'real_browser_rendering':False,'SVG_pixel_backend':'upstream pure GP VectorPen test fallback'}
 (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--editor',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
 p.add_argument('--node',default=shutil.which('node'));a=p.parse_args();assert a.node,'Node.js is required'
 result=run(a.editor.resolve(),a.output.resolve(),Path(__file__).resolve().parents[1],a.node)
 print(json.dumps({'status':result['status'],'cases':len(result['records'])}));sys.exit(0)
