#!/usr/bin/env python3
"""Cross-check the exact C RTC calendar helper against Python's datetime.

Requires a host C compiler (cc by default); does not build Zephyr or touch a board.
"""
# SPDX-License-Identifier: MIT
import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',default='cc')
    parser.add_argument('--wasi',action='store_true',help='Run a wasm32/WASI compiler output with installed wasmtime')
    args=parser.parse_args()
    compiler=shutil.which(args.compiler)
    if compiler is None:raise SystemExit('Host C compiler unavailable; calendar test NOT RUN')
    header=Path(__file__).resolve().parents[1]/'boards/waveshare_esp32s3_rlcd_4_2/bringup/src/rlcd_calendar.h'
    cases=[]
    current=date(2000,1,1)
    while current<date(2100,1,1):
        cases.append((current.year,current.month,current.day,23,59,59))
        current+=timedelta(days=1)
    for year in [1999,2000,2001,2004,2026,2099,2100,-2147483648,2147483647]:
        for month in [-1,0,1,2,4,12,13]:
            for day in [-1,0,28,29,30,31,32]:cases.append((year,month,day,0,0,0))
    for position, values in [(3,[-1,0,23,24]),(4,[-1,0,59,60]),(5,[-1,0,59,60])]:
        for value in values:
            case=[2026,10,18,0,0,0];case[position]=value;cases.append(tuple(case))
    expected=[]
    for y,m,d,h,minute,s in cases:
        try:
            valid=date(y,m,d)
            expected.append((valid.weekday()+1)%7 if 2000<=y<=2099 and 0<=h<24 and 0<=minute<60 and 0<=s<60 else -1)
        except (ValueError,OverflowError):expected.append(-1)
    with tempfile.TemporaryDirectory(prefix='rlcd-calendar-') as tmp:
        folder=Path(tmp)
        source=folder/'check.c'
        source.write_text('#include <stdio.h>\n#include "rlcd_calendar.h"\nint main(void) {\n'
            'int y,m,d,h,n,s; while (scanf("%d%d%d%d%d%d",&y,&m,&d,&h,&n,&s)==6) {\n'
            'printf("%d\\n",rlcd_utc_weekday(y,m,d,h,n,s)); } return 0; }\n')
        executable=folder/'calendar-check'
        subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',str(header.parent),str(source),'-o',str(executable)],check=True,capture_output=True)
        input_text='\n'.join(' '.join(map(str,c)) for c in cases)+'\n'
        if args.wasi:
            import wasmtime
            input_path=folder/'input.txt';input_path.write_text(input_text)
            output_path=folder/'output.txt'
            config=wasmtime.Config();config.consume_fuel=True
            engine=wasmtime.Engine(config);store=wasmtime.Store(engine);store.set_fuel(300_000_000)
            wasi=wasmtime.WasiConfig();wasi.stdin_file=str(input_path);wasi.stdout_file=str(output_path)
            wasi.stderr_file=str(folder/'stderr.txt');store.set_wasi(wasi)
            linker=wasmtime.Linker(engine);linker.define_wasi()
            module=wasmtime.Module.from_file(engine,str(executable))
            instance=linker.instantiate(store,module);instance.exports(store)['_start'](store)
            output=output_path.read_text()
        else:
            result=subprocess.run([str(executable)],input=input_text,check=True,capture_output=True,text=True)
            output=result.stdout
        actual=[int(x) for x in output.splitlines()]
    assert len(actual)==len(expected)
    for case, got, wanted in zip(cases,actual,expected):
        assert got==wanted,(case,got,wanted)
    print(json.dumps({'result':'PASS','cases':len(cases),'full_century_valid_dates':36525,
        'runtime':'wasm32/WASI' if args.wasi else 'native host',
        'scope':'Exact C date/range/weekday helper compared with independent Python datetime; no physical RTC claim'},indent=2))


if __name__=='__main__':main()
