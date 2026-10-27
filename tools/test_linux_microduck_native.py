#!/usr/bin/env python3
"""Sanitizer test of real native MicroDuck C jobs using private Unix fixtures.

The 40 ms test timeout and peer/write fault providers exist only in this harness;
the production source defaults to 10 seconds. No hardware or Pi access occurs.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('build-artifacts/microduck-native-tests'))
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1];output=args.output.resolve()
    sys.path.insert(0,str(repo/'linux/arm64'))
    spec=importlib.util.spec_from_file_location('microduck_test_build',repo/'linux/arm64/build.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    builder.prepare(args.upstream.resolve(),output,True)
    binary=output/'microduck-native-tests'
    command=['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
             '-fsanitize=address,undefined','-fno-omit-frame-pointer','-DMICRODUCK_TIMEOUT_MS=40',
             '-I'+str(output),'-I'+str(repo),'-include',str(repo/'common/json/json_config.h'),
             str(repo/'tests/linux_microduck_native.c'),str(output/'vm/arena.c'),str(output/'vm/mem.c'),
             str(repo/'third_party/yyjson/yyjson.c'),'-o',str(binary)]
    build=subprocess.run(command,capture_output=True,text=True)
    (output/'compile.log').write_text(build.stdout+build.stderr)
    if build.returncode:raise RuntimeError(build.stdout+build.stderr)
    environment=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30,env=environment)
    (output/'run.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    report=json.loads(result.stdout.strip().splitlines()[-1]);report.update(sanitizers=['address','undefined'],sanitizer_diagnostics=result.stderr,production_timeout_ms=10000,test_timeout_ms=40,physical_microduck=False)
    if args.evidence:args.evidence.parent.mkdir(parents=True,exist_ok=True);args.evidence.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
