"""Optional owned Python service for the existing managed Pi application."""
# SPDX-License-Identifier: MIT
import asyncio
import json
import os
from pathlib import Path


def inside(root,name):
    if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Python application paths must stay inside its installation')
    value=(root/name).resolve()
    if root not in value.parents:raise ValueError('Python application path escaped its installation')
    return value


class ManagedPython:
    def __init__(self,root,config):
        self.root=root;self.config=config;self.process=None;self.log=None;self.socket=None

    async def __aenter__(self):
        settings=self.config.get('python_extensions')
        if settings is None:return None
        if not isinstance(settings,dict) or set(settings)!={'profile','state','interpreter'}:raise ValueError('Configure Python profile, state and interpreter explicitly')
        profile=inside(self.root,settings['profile']);state=inside(self.root,settings['state'])
        interpreter=settings['interpreter']
        if not isinstance(interpreter,str) or not Path(interpreter).is_absolute() or not Path(interpreter).is_file():raise ValueError('Python extension interpreter must be an existing explicit local executable')
        original=self.config.get('microduck_socket')
        if original and json.loads(profile.read_text()).get('microduck_gateway')!=original:raise ValueError('Preserve the existing MicroDuck socket as microduck_gateway in the Python profile')
        state.mkdir(mode=0o700,exist_ok=True)
        if state.stat().st_uid!=os.geteuid() or state.stat().st_mode&0o077:raise ValueError('Python application state must be private and user owned')
        # Installed release: code/python_runtime.py + code/linux/extensions.
        # Source checkout: linux/arm64/python_runtime.py + linux/extensions.
        entry=Path(__file__).with_name('linux')/'extensions/service.py'
        if not entry.is_file():entry=Path(__file__).parents[1]/'extensions/service.py'
        if not entry.is_file():raise ValueError('This MicroBlocks package is missing its Python extension runtime')
        fd=os.open(state/'service.log',os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600);self.log=os.fdopen(fd,'ab',buffering=0)
        try:
            spawning=asyncio.create_task(asyncio.create_subprocess_exec(interpreter,str(entry),'--config',str(profile),'--state',str(state),stdout=asyncio.subprocess.PIPE,stderr=self.log,limit=4096))
            try:self.process=await asyncio.shield(spawning)
            except asyncio.CancelledError:
                self.process=await spawning
                raise
            raw=await asyncio.wait_for(self.process.stdout.readline(),5)
            if not raw:raise RuntimeError('Python extension service did not start; inspect its private service.log')
            ready=json.loads(raw)
            expected=str(state/'python.sock')
            if ready!={'ready':True,'pid':self.process.pid,'socket':expected}:raise RuntimeError('Python extension service did not report its owned private socket')
            self.socket=expected;return expected
        except BaseException:
            await self.__aexit__(None,None,None);raise

    async def __aexit__(self,*error):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:await asyncio.wait_for(self.process.wait(),3)
            except TimeoutError:self.process.kill();await self.process.wait()
        if self.log:self.log.close();self.log=None
