#!/usr/bin/env python3
"""Run real 32-bit SmallVM and I/O adapters with simulated drivers via WASI.

Needs the official WASI SDK and the Python wasmtime package. No board access.
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
    board=repo/'boards/waveshare_esp32s3_rlcd_4_2'
    with tempfile.TemporaryDirectory(prefix='smallvm-io-') as folder:
        work=Path(folder);prepared=work/'vm-source'
        prepare(args.source.resolve(),prepared)
        # Expose the recorded error only in this disposable simulation build.
        # failure() deliberately returns a boolean, not the VM error number.
        with (prepared/'vm/interp.c').open('a',encoding='utf-8',newline='\n') as stream:
            stream.write('\nunsigned smallvm_test_error(void) { return errorCode; }\n')
        sources=[prepared/'vm'/f'{n}.c' for n in ['interp','runtime','mem','persist','dataPrims','varPrims','tinyJSON','mbFont','boardHooks']]
        sources += [board/'smallvm/src/platform.c',board/'smallvm/src/generic_primitives.c',
            board/'integration/rlcd_smallvm_primitives.c',repo/'tests/vm_protocol_host.c']
        compiler=args.wasi_sdk.resolve()/'bin/clang'
        command=[str(compiler),'-O1','-DSMALLVM_ZEPHYR=1','-I'+str(prepared),
            '-I'+str(board/'bringup/src'),'-I'+str(board/'smallvm/src'),
            *map(str,sources),'-Wl,-z,stack-size=65536','-Wl,--max-memory=16777216','-o',str(work/'test.wasm')]
        build=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
        if build.returncode:
            raise RuntimeError(build.stdout+build.stderr)
        engine=wasmtime.Engine();store=wasmtime.Store(engine)
        config=wasmtime.WasiConfig();config.stdout_file=str(work/'stdout');config.inherit_stderr();store.set_wasi(config)
        linker=wasmtime.Linker(engine);linker.define_wasi()
        module=wasmtime.Module.from_file(engine,str(work/'test.wasm'))
        instance=linker.instantiate(store,module);instance.exports(store)['_start'](store)
        output=(work/'stdout').read_text()
        report=json.loads(output.strip().splitlines()[-1])
        fake=work/'fakes';fake.mkdir()
        for header in ['Arduino.h','zephyr/drivers/gpio.h','zephyr/drivers/i2c.h',
                'zephyr/drivers/spi.h','zephyr/drivers/pwm.h','zephyr/drivers/pinctrl.h']:
            path=fake/header;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('#include "generic_io_fakes.h"\n',encoding='utf-8',newline='\n')
        backend_command=[str(compiler.with_name('clang++')),'-O1','-std=c++17',
            '-I'+str(fake),'-I'+str(repo/'tests'),'-I'+str(board/'smallvm/src'),
            str(board/'smallvm/src/generic_io.cpp'),str(repo/'tests/generic_io_backend.cpp'),
            '-o',str(work/'backend.wasm')]
        backend_build=subprocess.run(backend_command,capture_output=True,text=True,encoding='utf-8')
        if backend_build.returncode:raise RuntimeError(backend_build.stdout+backend_build.stderr)
        backend_store=wasmtime.Store(engine);backend_wasi=wasmtime.WasiConfig()
        backend_wasi.stdout_file=str(work/'backend-stdout');backend_wasi.inherit_stderr();backend_store.set_wasi(backend_wasi)
        backend_module=wasmtime.Module.from_file(engine,str(work/'backend.wasm'))
        backend_instance=linker.instantiate(backend_store,backend_module)
        backend_instance.exports(backend_store)['_start'](backend_store)
        report['backend']=json.loads((work/'backend-stdout').read_text().strip().splitlines()[-1])
        report.update(compiler=str(compiler),compiler_warnings=build.stderr,
            adapter_sha256=hashlib.sha256((board/'smallvm/src/generic_primitives.c').read_bytes()).hexdigest(),
            source_commit='2071df569623ba9cdcd6f8106b61796e047df38b',
            hardware_claim='None: drivers are mocked; physical outputs and external wiring are untested')
        if args.evidence:
            args.evidence.parent.mkdir(parents=True,exist_ok=True)
            args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({k:v for k,v in report.items() if k!='compiler_warnings'},indent=2))

if __name__=='__main__':main()
