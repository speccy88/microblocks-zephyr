#!/usr/bin/env python3
"""One MicroBlocks foreground launcher owns the Python service automatically."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import json
from pathlib import Path
import signal
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]));__package__='linux.extensions'
from .service import Service,read_configuration


async def run(args):
    service=Service(read_configuration(args.config),args.state.resolve())
    child=None;stopped=asyncio.Event()
    for name in (signal.SIGTERM,signal.SIGINT):asyncio.get_running_loop().add_signal_handler(name,stopped.set)
    try:
        await service.start()
        # The existing session already forwards this private IPC endpoint to
        # its VM; browser/bridge/network policy remains owned by that launcher.
        # A venv's interpreter is commonly a symlink. Resolving it would lose
        # the environment and its already-approved WebSocket dependency.
        interpreter=str(args.session_python.absolute()) if args.session_python else sys.executable
        command=[interpreter,str(Path(__file__).parents[1]/'arm64/session.py'),
            '--binary',str(args.binary.resolve()),'--editor',str(args.editor.resolve()),
            '--data',str(args.data.resolve()),'--port',str(args.port),
            '--microduck-socket',str(service.path)]
        if args.resume:command.append('--resume')
        child=await asyncio.create_subprocess_exec(*command)
        waiter=asyncio.create_task(child.wait());stopper=asyncio.create_task(stopped.wait())
        await asyncio.wait([waiter,stopper],return_when=asyncio.FIRST_COMPLETED)
        stopper.cancel();await asyncio.gather(stopper,return_exceptions=True)
    finally:
        if child and child.returncode is None:
            child.terminate()
            try:await asyncio.wait_for(child.wait(),10)
            except TimeoutError:child.kill();await child.wait()
        await service.close()
    if child and child.returncode:raise RuntimeError('MicroBlocks session stopped unexpectedly; inspect its own logs')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','state','binary','editor','data'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--port',type=int,default=8876);p.add_argument('--resume',action='store_true')
    p.add_argument('--session-python',type=Path,help='Existing approved Python environment for the WebSocket session')
    try:asyncio.run(run(p.parse_args()))
    except (OSError,ValueError,RuntimeError) as error:p.exit(1,'MicroBlocks Python setup: '+str(error)+'\n')
