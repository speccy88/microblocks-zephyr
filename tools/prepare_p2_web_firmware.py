"""Build the pinned native P2 browser images; never opens a board or flashes."""
# SPDX-License-Identifier: MIT
import argparse
import json
from pathlib import Path
import subprocess
import shutil
from build_propeller2 import build

ROOT=Path(__file__).resolve().parents[1]


def prepare(output,compiler=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    pin=json.loads((ROOT/'dependencies/p2-web-installer.json').read_text(encoding='utf-8'))
    if compiler is None:
        if not shutil.which('make') or not shutil.which('bison'):
            raise RuntimeError('Pinned FlexC source build requires make, a C/C++ compiler and bison')
        source=output/'compiler-source'
        if not source.exists():
            source.mkdir()
            for args in [['init'],['remote','add','origin',pin['compiler_repository']],
                         ['fetch','--depth=1','origin',pin['compiler_commit']],['checkout','--detach','FETCH_HEAD']]:
                subprocess.run(['git','-C',str(source),*args],check=True)
        actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        if actual!=pin['compiler_commit']:
            raise ValueError('Choose a fresh output directory; compiler source pin differs')
        subprocess.run(['make','-C',str(source),'-j2','build/flexcc','build/flexspin'],check=True)
        compiler=source/'build/flexcc'
    reports={}
    for board,expected in pin['expected_images'].items():
        report=build(Path(compiler),board,output)
        if report['sha256']!=expected['sha256'] or report['bytes']!=expected['bytes']:
            raise ValueError('Native P2 binary differs from the reviewed/tested image: '+board)
        reports[board]=report
    (output/'installer-build.json').write_text(json.dumps({'pin':pin,'images':reports},indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'boards':list(reports),'hashes_match_reviewed_images':True,'physical_hardware':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--flexcc',type=Path)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.flexcc)))
