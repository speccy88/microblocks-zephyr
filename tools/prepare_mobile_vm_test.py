#!/usr/bin/env python3
"""Native VM fixture with honest display-off cleanup; no simulated execution."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys


def prepare(linux_source, upstream, output, sanitize=False):
    module_dir=linux_source/'linux/arm64'
    sys.path.insert(0,str(module_dir.resolve()))
    spec=importlib.util.spec_from_file_location('pinned_mobile_vm_build',module_dir/'build.py')
    build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
    report=build.prepare(upstream.resolve(),output.resolve(),sanitize)
    path=output/'platform/primitives.c';raw=path.read_text()
    anchor='UNSUPPORTED_N(primMBDisplay) UNSUPPORTED_N(primMBDisplayOff) UNSUPPORTED_N(primMBEnableDisplay)'
    if raw.count(anchor)!=1:raise ValueError('Review changed headless display fixture')
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    if before!='090061b4c2788d1bb05ca23afba1b951fa086f44235e86bae78c297e19b4cfe8':
        raise ValueError('Review changed pinned native hardware stubs')
    # v417 deleteAllCodeMsg invokes primMBDisplayOff(0,NULL) OUTSIDE a task.
    # The pinned headless stub sets a global task error there and poisons the
    # next real program. There is no physical display to clear in this fixture.
    raw=raw.replace(anchor,'''UNSUPPORTED_N(primMBDisplay) UNSUPPORTED_N(primMBEnableDisplay)
OBJ primMBDisplayOff(int n,OBJ *a){
 if(n==0 && a==NULL)return falseObj; /* Runtime delete-all cleanup only. */
 return fail(primitiveNotImplemented); /* Explicit hardware use stays unsupported. */
}''')
    path.write_text(raw,encoding='utf-8',newline='\n')
    after=hashlib.sha256(path.read_bytes()).hexdigest()
    report['sources']['platform/primitives.c']['prepared_sha256']=after
    report['fixture_overlay']={'scope':'headless display-off cleanup outside a task',
        'source_before_sha256':before,'source_after_sha256':after,
        'arithmetic_or_protocol_simulated':False,'explicit_hardware_use_supported':False}
    path=output/'platform/self_test.c';raw=path.read_text()
    anchor='int linuxPlatformSelfTest(void){'
    if raw.count(anchor)!=1:raise ValueError('Review changed native fixture self-test')
    raw=raw.replace(anchor,anchor+'''
 OBJ absent=falseObj;fail(0);primMBDisplayOff(0,NULL);
 if(failure())return 1;
 primMBDisplayOff(0,&absent);if(!failure())return 1;fail(0);
''')
    path.write_text(raw,encoding='utf-8',newline='\n')
    report['sources']['platform/self_test.c']['prepared_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    (output/'source-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--linux-source',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--sanitize',action='store_true')
    p.add_argument('--source-only',action='store_true');p.add_argument('--test',action='store_true')
    a=p.parse_args();r=prepare(a.linux_source,a.upstream,a.output,a.sanitize)
    if not a.source_only:
        if platform.system()!='Linux':raise RuntimeError('Compile on Linux or request --source-only')
        subprocess.run(['sh',str(a.output.resolve()/'build.sh')],check=True)
        if a.test:subprocess.run([str(a.output.resolve()/'smallvm'),'--self-test'],check=True,timeout=30)
        r.update(build_host=platform.machine(),self_test='PASS' if a.test else 'not run',
                 binary_sha256=hashlib.sha256((a.output/'smallvm').read_bytes()).hexdigest())
        (a.output/'build-manifest.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'compiled':not a.source_only,'fixture_overlay':r['fixture_overlay']}))


if __name__=='__main__':main()
