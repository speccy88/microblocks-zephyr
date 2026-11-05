"""Build the pinned native P2 browser images; never opens a board or flashes."""
# SPDX-License-Identifier: MIT
import argparse
import json
from pathlib import Path
import subprocess
import shutil
import hashlib
import importlib.util
import io
import re
import tarfile
import tempfile
from build_propeller2 import build

ROOT=Path(__file__).resolve().parents[1]


def reviewed_sources(pin, destination):
    """Materialize the approved native source, without switching the checkout."""
    commit=pin.get('firmware_source_commit','')
    if not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('Reviewed firmware needs an exact source commit')
    available=subprocess.run(['git','-C',str(ROOT),'cat-file','-e',commit+'^{tree}'],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if available.returncode:
        subprocess.run(['git','-C',str(ROOT),'fetch','--no-tags','--depth=1',
                        'https://github.com/speccy88/microblocks-zephyr.git',commit],check=True)
    raw=subprocess.check_output(['git','-C',str(ROOT),'archive','--format=tar',commit,
                                 'boards/propeller2/native','tools/build_propeller2.py'])
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        archive.extractall(destination,filter='data')
    hashes={p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((destination/'boards/propeller2/native').rglob('*'))
            if p.is_file() and p.suffix in {'.c','.h'}}
    return {'firmware_source_commit':commit,'native_sources_sha256':hashes}


def prepare(output,compiler=None,candidate_output=None):
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
        # Direct executable targets do not depend on upstream's all/dirs rule.
        (source/'build').mkdir(exist_ok=True)
        subprocess.run(['make','-C',str(source),'-j2','build/flexcc','build/flexspin'],check=True)
        compiler=source/'build/flexcc'
    reports={}
    with tempfile.TemporaryDirectory(prefix='reviewed-vm-',dir=output) as temporary:
        source=Path(temporary)
        provenance=reviewed_sources(pin,source)
        spec=importlib.util.spec_from_file_location('reviewed_p2_builder',source/'tools/build_propeller2.py')
        approved=importlib.util.module_from_spec(spec);spec.loader.exec_module(approved)
        for board,expected in pin['expected_images'].items():
            report=approved.build(Path(compiler),board,output)
            if report['sha256']!=expected['sha256'] or report['bytes']!=expected['bytes']:
                raise ValueError('Native P2 binary differs from the reviewed/tested image: '+board)
            reports[board]=report
    (output/'reviewed-native-source.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
    (output/'installer-build.json').write_text(json.dumps({'pin':pin,'images':reports},indent=2)+'\n',encoding='utf-8',newline='\n')
    candidates={}
    if candidate_output is not None:
        for board in pin['expected_images']:
            candidates[board]=build(Path(compiler),board,Path(candidate_output))
    return {'boards':list(reports),'hashes_match_reviewed_images':True,'physical_hardware':False,
            'candidate_boards_compiled':list(candidates),'candidate_images_published':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--flexcc',type=Path)
    p.add_argument('--candidate-output',type=Path,help='Compile current sources separately; never package these images')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.flexcc,a.candidate_output)))
