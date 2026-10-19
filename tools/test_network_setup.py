#!/usr/bin/env python3
"""Compile/run the actual portable setup/store against synthetic RAM fixtures."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def unix_path(path):
    path = path.resolve()
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:] if os.name == 'nt' else str(path)


def node_wasi(node, binary, cwd):
    script = """
const {WASI}=require('node:wasi'),fs=require('node:fs');
const bytes=fs.readFileSync(0);
const wasi=new WASI({version:'preview1',args:['network-setup-test'],env:{},preopens:{},returnOnExit:true});
(async()=>{
 const module=await WebAssembly.compile(bytes);
 const instance=await WebAssembly.instantiate(module,{wasi_snapshot_preview1:wasi.wasiImport});
 process.exitCode=wasi.start(instance);
})().catch(error=>{process.stderr.write(error.name+': '+error.message+'\\n');process.exitCode=1;});
"""
    execution = subprocess.run([node, '--no-warnings', '-e', script], cwd=cwd,
                               input=binary, capture_output=True, timeout=20)
    if execution.returncode:
        raise RuntimeError(execution.stderr.decode('utf-8', errors='replace').strip() or 'WASI fixture returned a failure')
    return execution.stdout.decode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--native-compiler')
    group.add_argument('--wasi-sdk')
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--node', help='Use an existing Node WASI runtime instead of Python wasmtime')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    if args.wsl and not args.wasi_sdk:
        parser.error('--wsl requires --wasi-sdk')
    if args.node and not args.wasi_sdk:
        parser.error('--node requires --wasi-sdk')
    repo = Path(__file__).resolve().parents[1]
    sources = [repo / name for name in ('common/network_setup.c', 'common/network_setup_store.c',
                                       'tests/network_setup_host.c')]
    translate = unix_path if args.wsl else lambda p: str(p.resolve())
    with tempfile.TemporaryDirectory(prefix='mb-network-setup-') as temporary:
        work = Path(temporary)
        output = work / ('test.wasm' if args.wasi_sdk else 'test.exe' if os.name == 'nt' else 'test')
        compiler = ['wsl.exe', '--exec', args.wasi_sdk.rstrip('/') + '/bin/clang'] if args.wsl else [
            str(Path(args.wasi_sdk) / 'bin/clang') if args.wasi_sdk else args.native_compiler]
        command = compiler + ['-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
                              '-I' + translate(repo / 'common'), *map(translate, sources)]
        if args.wasi_sdk:
            command += ['-Wl,-z,stack-size=65536', '-Wl,--max-memory=1048576']
        command += ['-o', translate(output)]
        subprocess.run(command, check=True, timeout=45)
        if not output.is_file():
            raise RuntimeError('Compiler returned without creating the requested test artifact')
        if args.wasi_sdk and args.node:
            result = node_wasi(args.node, output.read_bytes(), repo)
        elif args.wasi_sdk:
            import wasmtime
            config = wasmtime.Config(); config.consume_fuel = True
            engine = wasmtime.Engine(config); store = wasmtime.Store(engine); store.set_fuel(100000000)
            wasi = wasmtime.WasiConfig(); wasi.stdout_file = str(work / 'stdout'); wasi.inherit_stderr()
            store.set_wasi(wasi); linker = wasmtime.Linker(engine); linker.define_wasi()
            instance = linker.instantiate(store, wasmtime.Module.from_file(engine, str(output)))
            instance.exports(store)['_start'](store)
            result = (work / 'stdout').read_text(encoding='utf-8')
        else:
            result = subprocess.run([str(output)], check=True, capture_output=True, text=True, timeout=20).stdout
        report = json.loads(result)
        report.update(command=command, runtime='Node WASI' if args.node else 'Wasmtime' if args.wasi_sdk else 'native',
                      scope='Portable C decoder and two-slot plaintext journal; RAM I/O only; no firmware integration or device/credential access',
                      source_sha256={p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sources + [repo / 'common/network_setup.h', repo / 'common/network_setup_store.h']})
        if args.evidence:
            args.evidence.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
