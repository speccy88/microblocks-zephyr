#!/usr/bin/env python3
"""Apply reviewed native P4 fixes to the exact pinned Zephyr checkout."""
# SPDX-License-Identifier: MIT
import argparse,subprocess
from pathlib import Path
PIN='a915b2f12675b48b16d56653ea145dcd8f20cbbf'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--zephyr',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--require-applied',action='store_true');a=p.parse_args()
 root=a.zephyr.resolve();repo=Path(__file__).resolve().parents[1]
 def git(*args):return subprocess.run(['git','-C',str(root),*map(str,args)],capture_output=True,text=True)
 result=git('rev-parse','HEAD')
 if result.returncode or result.stdout.strip()!=PIN:raise SystemExit('Requires exact pinned Zephyr '+PIN)
 for patch in sorted((repo/'boards/waveshare_esp32p4_wifi6/zephyr/patches').glob('*.patch')):
  if git('apply','--reverse','--check',patch).returncode==0:print(patch.name+': already applied');continue
  if a.require_applied:raise SystemExit('Required native P4 patch is not applied: '+patch.name+'; run this tool with --execute first')
  check=git('apply','--check',patch)
  if check.returncode:raise SystemExit('Patch conflicts; preserving checkout: '+patch.name+'\n'+check.stderr)
  if a.execute:
   result=git('apply',patch)
   if result.returncode:raise SystemExit(result.stderr)
   print(patch.name+': applied')
  else:print(patch.name+': ready; add --execute to apply (no hardware/network action)')
