#!/usr/bin/env python3
"""Compile/run the real 32-bit Fruit Jam VM adapters with simulated hardware.

Uses WASI SDK and wasmtime. Does not exercise USB electrical behavior or drivers.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from prepare_smallvm import prepare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--wasi-sdk',required=True,type=Path)
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args()
    import wasmtime
    repo=Path(__file__).resolve().parents[1]
    board=repo/'boards/adafruit_fruit_jam/smallvm/src'
    with tempfile.TemporaryDirectory(prefix='fruitjam-vm-') as folder:
        work=Path(folder);prepared=work/'vm-source'
        prepare(args.source.resolve(),prepared,strict_digital_arity=True)
        with (prepared/'vm/interp.c').open('a',encoding='utf-8',newline='\n') as stream:
            stream.write('\nunsigned smallvm_test_error(void) { return errorCode; }\n')
        sources=[prepared/'vm'/f'{n}.c' for n in ['interp','runtime','mem','persist',
                 'dataPrims','varPrims','tinyJSON','mbFont','boardHooks']]
        sources += [board/'platform.c',board/'generic_primitives.c',repo/'tests/fruit_jam_vm_host.c']
        compiler=args.wasi_sdk.resolve()/'bin/clang'
        command=[str(compiler),'-O1','-DSMALLVM_ZEPHYR=1','-I'+str(prepared),'-I'+str(board),
                 *map(str,sources),'-Wl,-z,stack-size=65536','-Wl,--max-memory=16777216',
                 '-o',str(work/'test.wasm')]
        build=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
        if build.returncode:raise RuntimeError(build.stdout+build.stderr)
        engine=wasmtime.Engine();store=wasmtime.Store(engine)
        config=wasmtime.WasiConfig();config.stdout_file=str(work/'stdout');config.inherit_stderr()
        store.set_wasi(config);linker=wasmtime.Linker(engine);linker.define_wasi()
        module=wasmtime.Module.from_file(engine,str(work/'test.wasm'))
        instance=linker.instantiate(store,module);instance.exports(store)['_start'](store)
        report=json.loads((work/'stdout').read_text().strip().splitlines()[-1])
        report.update(command=command,compiler_warnings=build.stderr,
            adapter_sha256=hashlib.sha256((board/'generic_primitives.c').read_bytes()).hexdigest(),
            source_commit='2071df569623ba9cdcd6f8106b61796e047df38b',
            native_digital_arity_checks=4,
            hardware_claim='None: simulated transport/buttons/I2C/ADC/PWM; real USB and GPIO drivers are untested')
        if args.evidence:args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({k:v for k,v in report.items() if k!='compiler_warnings'},indent=2))


if __name__=='__main__':main()
