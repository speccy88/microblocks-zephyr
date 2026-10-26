#!/usr/bin/env python3
"""Apply reviewed native P4 fixes to the exact pinned Zephyr checkout."""
# SPDX-License-Identifier: MIT
import argparse,re,subprocess,tempfile
from pathlib import Path
PIN='a915b2f12675b48b16d56653ea145dcd8f20cbbf'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--zephyr',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--require-applied',action='store_true');a=p.parse_args()
 root=a.zephyr.resolve();repo=Path(__file__).resolve().parents[1]
 def git(*args):return subprocess.run(['git','-C',str(root),*map(str,args)],capture_output=True,text=True)
 result=git('rev-parse','HEAD')
 if result.returncode or result.stdout.strip()!=PIN:raise SystemExit('Requires exact pinned Zephyr '+PIN)
 patches=sorted((repo/'boards/waveshare_esp32p4_wifi6/zephyr/patches').glob('*.patch'))
 # Later patches may intentionally change earlier added hunks. Reconstruct
 # the complete pinned series in isolation before checking individual patches.
 paths={name for patch in patches for name in re.findall(r'^\+\+\+ b/(.+)$',patch.read_text(),re.M)}
 with tempfile.TemporaryDirectory(prefix='p4-zephyr-patch-series-') as folder:
  expected=Path(folder)
  for name in paths:
   target=expected/name;target.parent.mkdir(parents=True,exist_ok=True)
   target.write_bytes(subprocess.check_output(['git','-C',str(root),'show',PIN+':'+name]))
  for patch in patches:
   result=subprocess.run(['git','apply',str(patch.resolve())],cwd=expected,capture_output=True,text=True)
   if result.returncode:raise SystemExit('Invalid pinned patch series: '+patch.name+'\n'+result.stderr)
  complete=all((root/name).read_bytes()==(expected/name).read_bytes() for name in paths)
 if complete:
  print('Complete pinned native P4 patch series applied ('+str(len(patches))+' patches)');raise SystemExit(0)
 for patch in patches:
  if git('apply','--reverse','--check',patch).returncode==0:print(patch.name+': already applied');continue
  if a.require_applied:raise SystemExit('Required native P4 patch is not applied: '+patch.name+'; run this tool with --execute first')
  check=git('apply','--check',patch)
  if check.returncode:raise SystemExit('Patch conflicts; preserving checkout: '+patch.name+'\n'+check.stderr)
  if a.execute:
   result=git('apply',patch)
   if result.returncode:raise SystemExit(result.stderr)
   print(patch.name+': applied')
  else:print(patch.name+': ready; add --execute to apply (no hardware/network action)')
