#!/usr/bin/env python3
"""Run bounded native HTTP/WebSocket/NINA protocol fixtures in 32-bit WASI."""
# SPDX-License-Identifier: MIT
import argparse,json,subprocess,tempfile,hashlib
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wasi-sdk',required=True,type=Path);p.add_argument('--evidence',required=True,type=Path);a=p.parse_args()
    import wasmtime
    repo=Path(__file__).resolve().parents[1];board=repo/'boards/adafruit_fruit_jam/smallvm/src'
    sources=[board/'http_protocol.c',board/'nina_socket_protocol.c',repo/'tests/fruit_jam_network_protocol.c']
    with tempfile.TemporaryDirectory(prefix='fruitjam-network-') as folder:
        w=Path(folder);cmd=[str(a.wasi_sdk.resolve()/'bin/clang'),'-O1','-Wall','-Wextra','-Werror','-I'+str(board),*map(str,sources),'-Wl,-z,stack-size=65536','-Wl,--max-memory=1048576','-o',str(w/'test.wasm')]
        subprocess.run(cmd,check=True,timeout=45)
        config=wasmtime.Config();config.consume_fuel=True;engine=wasmtime.Engine(config);store=wasmtime.Store(engine);store.set_fuel(10000000)
        wasi=wasmtime.WasiConfig();wasi.stdout_file=str(w/'stdout');wasi.inherit_stderr();store.set_wasi(wasi)
        linker=wasmtime.Linker(engine);linker.define_wasi();instance=linker.instantiate(store,wasmtime.Module.from_file(engine,str(w/'test.wasm')));instance.exports(store)['_start'](store)
        report=json.loads((w/'stdout').read_text());report['command']=cmd
        report['source_sha256']={str(x.relative_to(repo)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources}
        a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
