#!/usr/bin/env python3
"""Configured Python operations over private same-user Unix RPC, never TCP."""
# SPDX-License-Identifier: MIT
import asyncio
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]));__package__='linux.extensions'
from .api import Context,ExtensionError,MAX_REQUEST,MAX_REPLY,bounded_json,failure
from linux.microduck.protocol import RpcError,decode,encode,peer_uid,read_message

NAME=re.compile(r'^[a-z][a-z0-9_.-]{0,63}$')
FACTORY=re.compile(r'^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*$')


def configuration(value):
    if sys.version_info<(3,11):raise ValueError('Python extension service requires Python 3.11 or newer')
    if not isinstance(value,dict) or set(value)-{'schema','board','extensions','microduck_gateway'} or value.get('schema')!=1 or value.get('board') not in ('pi5','microduck','linux-test'):
        raise ValueError('Expected version 1 Python configuration and an explicit board profile')
    entries=value.get('extensions')
    if not isinstance(entries,dict) or not 1<=len(entries)<=8:raise ValueError('Configure one through eight named extensions')
    for name,entry in entries.items():
        if not isinstance(name,str) or not NAME.fullmatch(name) or not isinstance(entry,dict) or set(entry)-{'factory','settings','timeout','enabled'} or not isinstance(entry.get('factory'),str) or not FACTORY.fullmatch(entry['factory']) or not isinstance(entry.get('settings',{}),dict) or type(entry.get('enabled',True)) is not bool:
            raise ValueError('Invalid trusted extension factory or settings')
        timeout=entry.get('timeout',3)
        if type(timeout) not in (int,float) or not .1<=timeout<=8:raise ValueError('Operation timeout must be 0.1 through 8 seconds')
        bounded_json(entry,MAX_REQUEST)
    upstream=value.get('microduck_gateway')
    if upstream is not None and (type(upstream) is not str or not Path(upstream).is_absolute()):raise ValueError('MicroDuck upstream must be an explicit private absolute socket')
    return value


def read_configuration(path):
    path=Path(path).resolve(strict=True);s=path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022 or s.st_size>32768:raise ValueError('Python configuration must be a bounded trusted user-owned file')
    return configuration(json.loads(path.read_text(encoding='utf-8')))


def private_state(path):
    path=Path(path)
    if not path.is_absolute() or path.resolve()!=path:raise ValueError('Canonical absolute Python state directory required')
    path.mkdir(mode=0o700,parents=False,exist_ok=True);s=path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)!=0o700:raise ValueError('Python state must be a private owned directory (0700)')
    if len(os.fsencode(str(path/'python.sock')))>=108:raise ValueError('Python state path is too long for a Unix socket')
    return path


class Worker:
    def __init__(self,entry,context):
        self.entry,self.context=entry,context;self.process=None;self.busy=False;self.stderr=None;self.quarantined=False

    async def stop(self):
        process=self.process
        if process:
            if process.returncode is None:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:
                await asyncio.wait_for(process.wait(),.75)
                self.process=None;self.quarantined=False
            except TimeoutError:self.quarantined=True
        if self.stderr:
            self.stderr.cancel();await asyncio.gather(self.stderr,return_exceptions=True);self.stderr=None

    async def discard_stderr(self,stream):
        while await stream.read(4096):pass

    async def start(self):
        if self.quarantined and self.process and self.process.returncode is None:raise ExtensionError('worker_unavailable','The previous Python worker has not exited; check its device or system before another operation','not_sent')
        if self.process and self.process.returncode is None:return
        await self.stop()
        spawning=asyncio.create_task(asyncio.create_subprocess_exec(sys.executable,str(Path(__file__).with_name('worker.py')),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
            start_new_session=True,limit=MAX_REPLY+1))
        try:self.process=await asyncio.shield(spawning)
        except asyncio.CancelledError:
            self.process=await spawning # retain ownership if cancellation races process creation
            raise
        self.stderr=asyncio.create_task(self.discard_stderr(self.process.stderr))
        config={'factory':self.entry['factory'],'settings':self.entry.get('settings',{}),'state':str(self.context.state),'board':self.context.board}
        self.process.stdin.write(bounded_json(config,MAX_REQUEST)+b'\n');await self.process.stdin.drain()
        ready=decode(await self.process.stdout.readline(),MAX_REPLY)
        if ready!={'ready':True}:
            if isinstance(ready,dict) and ready.get('ok') is False:
                raise ExtensionError(ready['error']['code'],ready['error']['message'],ready['error']['outcome'])
            raise ExtensionError('worker_start','Python extension did not start correctly')

    async def call(self,method,args):
        if self.busy:return failure(ExtensionError('busy','Python extension is busy; wait before starting another operation','not_sent'))
        self.busy=True;sent=False
        try:
            async with asyncio.timeout(self.entry.get('timeout',3)):
                await self.start()
                raw=bounded_json({'method':method,'args':args},MAX_REQUEST)+b'\n'
                sent=True;self.process.stdin.write(raw);await self.process.stdin.drain()
                reply=decode(await self.process.stdout.readline(),MAX_REPLY)
                if not isinstance(reply,dict) or type(reply.get('ok')) is not bool:raise ValueError('Invalid worker result')
                bounded_json(reply)
                return reply
        except BaseException as error:
            await self.stop()
            if isinstance(error,asyncio.CancelledError):raise
            if isinstance(error,TimeoutError):return failure(ExtensionError('timeout','Python operation timed out; its worker was stopped. A write may have completed; do not retry automatically','unknown' if sent else 'not_sent'))
            return failure(error)
        finally:self.busy=False


class Service:
    def __init__(self,config,state):
        self.config=configuration(config);self.state=private_state(state);self.path=self.state/'python.sock'
        self.workers={};self.server=None;self.lock=None;self.active=0;self.clients=set();self.socket_identity=None
        context=Context(self.state,config['board'])
        for name,entry in config['extensions'].items():
            if entry.get('enabled',True):self.workers[name]=Worker(entry,context)

    async def start(self):
        self.lock=os.open(self.state/'.python.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:os.close(self.lock);self.lock=None;raise ValueError('This Python extension service is already running')
        if self.path.exists() or self.path.is_symlink():
            s=self.path.lstat()
            if not stat.S_ISSOCK(s.st_mode) or s.st_uid!=os.geteuid():raise ValueError('Refusing an unowned existing Python socket path')
            self.path.unlink()
        self.server=await asyncio.start_unix_server(self.handle,str(self.path),limit=MAX_REQUEST+1,backlog=8)
        self.path.chmod(0o600);s=self.path.lstat();self.socket_identity=(s.st_dev,s.st_ino);return self

    async def close(self):
        server=self.server
        if server:server.close();self.server=None
        clients=list(self.clients)
        for client in clients:client.cancel()
        await asyncio.gather(*clients,return_exceptions=True)
        await asyncio.gather(*(worker.stop() for worker in self.workers.values()))
        if server:await server.wait_closed()
        if self.lock is not None:
            if self.path.exists():
                s=self.path.lstat()
                if (s.st_dev,s.st_ino)==self.socket_identity:self.path.unlink()
            os.close(self.lock);self.lock=None

    async def dispatch(self,request):
        if not isinstance(request,dict) or set(request)-{'jsonrpc','id','method','params','confirmed'} or request.get('jsonrpc')!='2.0' or type(request.get('id')) is not int or not 1<=request['id']<=1073741823 or type(request.get('confirmed',False)) is not bool:
            raise ExtensionError('request','Invalid Python extension request')
        method,params=request.get('method'),request.get('params',{})
        if method=='extensions.capabilities':
            if params!={}:raise ExtensionError('arguments','Capabilities takes no arguments')
            result={'ok':True,'value':{'board':self.config['board'],'extensions':{name:{'enabled':name in self.workers,'factory':entry['factory']} for name,entry in self.config['extensions'].items()},'hardware_validated':False}}
        elif method=='extensions.call':
            if not isinstance(params,dict) or set(params)!={'extension','method','args'} or any(not isinstance(params[k],str) or not NAME.fullmatch(params[k]) for k in ('extension','method')) or not isinstance(params['args'],dict):raise ExtensionError('arguments','Invalid extension name, method or arguments')
            worker=self.workers.get(params['extension'])
            result=await worker.call(params['method'],params['args']) if worker else failure(ExtensionError('extension_missing','This Python extension is not enabled in the board configuration'))
        elif self.config.get('microduck_gateway'):
            from linux.microduck.client import Client
            client=Client(self.config['microduck_gateway'],timeout=8);client.next_id=request['id']
            try:value=await client.call(method,params,request.get('confirmed',False))
            except RpcError as error:return {'jsonrpc':'2.0','id':request['id'],'error':{'code':error.code,'message':'MicroDuck service refused the request','data':{'outcome':error.outcome}}}
            reply={'jsonrpc':'2.0','id':request['id'],'result':value}
            if client.last_metadata:reply['gateway']=client.last_metadata
            return reply
        else:raise ExtensionError('operation_missing','This operation is not provided by the Python extension service')
        return {'jsonrpc':'2.0','id':request['id'],'result':result}

    async def handle(self,reader,writer):
        task=asyncio.current_task();self.clients.add(task);self.active+=1;request_id=0
        try:
            if peer_uid(writer.get_extra_info('socket'))!=os.geteuid():raise ExtensionError('peer','Python extension requires the same local user')
            if self.active>4:raise ExtensionError('busy','Python service is busy; wait before another operation','not_sent')
            async with asyncio.timeout(9):
                request=await read_message(reader,MAX_REQUEST)
                if isinstance(request,dict) and type(request.get('id')) is int:request_id=request['id']
                response=await self.dispatch(request)
        except BaseException as error:
            if isinstance(error,asyncio.CancelledError):raise
            response={'jsonrpc':'2.0','id':request_id,'result':failure(error)}
        finally:
            self.active-=1
            if task.cancelling():
                writer.close();self.clients.discard(task)
        try:
            writer.write(encode(response,65536));await writer.drain()
        except (OSError,ValueError,RpcError):pass
        finally:
            writer.close()
            try:await writer.wait_closed()
            except OSError:pass
            self.clients.discard(task)


async def serve(args):
    service=Service(read_configuration(args.config),args.state.absolute())
    stopped=asyncio.Event();loop=asyncio.get_running_loop()
    for name in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(name,stopped.set)
    try:
        await service.start()
        print(json.dumps({'ready':True,'pid':os.getpid(),'socket':str(service.path)}),flush=True)
        await stopped.wait()
    finally:await service.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path);parser.add_argument('--state',required=True,type=Path)
    try:asyncio.run(serve(parser.parse_args()))
    except (OSError,ValueError,RuntimeError) as error:parser.exit(1,'MicroBlocks Python setup: '+str(error)+'\n')
