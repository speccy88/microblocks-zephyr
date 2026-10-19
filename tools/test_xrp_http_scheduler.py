#!/usr/bin/env python3
"""Compile actual generated scheduler functions with synthetic callback/send I/O."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
from test_network_setup import unix_path,node_wasi

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated',required=True,type=Path)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--wasi-sdk');group.add_argument('--native-compiler')
    p.add_argument('--wsl',action='store_true');p.add_argument('--node')
    p.add_argument('--evidence',required=True,type=Path)
    args=p.parse_args();repo=Path(__file__).resolve().parents[1]
    if args.wsl and not args.wasi_sdk:p.error('--wsl requires --wasi-sdk')
    if args.wasi_sdk and not args.node:p.error('--wasi-sdk requires --node')
    source=(args.generated/'http_server_http1.c').read_text(encoding='utf8')
    expected=json.loads((args.generated/'provenance.json').read_text())['sources']['http_server_http1.c']['generated_sha256']
    assert hashlib.sha256(source.encode()).hexdigest()==expected
    fragment=source[source.index('/* XRP: one response chunk'):source.index('static int dynamic_post_put_req(')]
    fixture=repo/'tests/xrp_http_scheduler_host.c'
    with tempfile.TemporaryDirectory(prefix='xrp-http-scheduler-') as tmp:
        work=Path(tmp);(work/'http_scheduler_under_test.inc').write_text(fragment,encoding='utf8',newline='\n')
        binary=work/('scheduler.wasm' if args.wasi_sdk else 'scheduler');translate=unix_path if args.wsl else lambda p:str(p.resolve())
        compiler=['wsl.exe','--exec',args.wasi_sdk.rstrip('/')+'/bin/clang'] if args.wsl else [str(Path(args.wasi_sdk)/'bin/clang') if args.wasi_sdk else args.native_compiler]
        command=compiler+['-std=c11','-O1','-Wall','-Wextra','-Werror','-I'+translate(work),translate(fixture)]
        if args.wasi_sdk:command+=['-Wl,-z,stack-size=65536','-Wl,--max-memory=1048576']
        command+=['-o',translate(binary)]
        subprocess.run(command,check=True,timeout=45)
        output=node_wasi(args.node,binary.read_bytes(),repo) if args.wasi_sdk else subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=15).stdout
        report=json.loads(output)
    report.update(scope='Actual generated HTTP/1 scheduler functions; synthetic callbacks/sends only; no framing/network/hardware claim',runtime='Node WASI' if args.wasi_sdk else 'native',command=command,
        generated_source_sha256=expected,fragment_sha256=hashlib.sha256(fragment.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest())
    args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
