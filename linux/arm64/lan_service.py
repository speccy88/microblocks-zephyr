#!/usr/bin/env python3
"""Managed permanent LAN runtime behind the existing local Caddy listener.

Starts/stops only its own child VM. Configuration, code, executable, assets and
data belong to one private installation root; no network/firewall configuration.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time

from lan_editor import LanEditor, LoopbackProxyPolicy, Policy
from browser_update import BrowserUpdater, UpdateError, begin_boot, confirm_boot
from python_runtime import ManagedPython


def private_root(path):
    root = Path(path).resolve(strict=True)
    meta = root.stat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077:
        raise RuntimeError('Managed installation must be private and current-user owned')
    return root


def selected(root, name):
    raw = Path(name)
    if raw.is_absolute() or '..' in raw.parts:
        raise RuntimeError('Managed paths must stay within their installation')
    target = (root / raw).resolve(strict=True)
    if root not in target.parents:
        raise RuntimeError('Managed path escaped its installation')
    return target


def atomic_state(root, state):
    temporary = root / 'run/.status-next.json'
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    os.replace(temporary, root / 'run/status.json')


def vm_arguments(config, binary, data, info):
    args = [str(binary), '--data-dir', str(data), '--pty-info', str(info)]
    socket = config.get('microduck_socket')
    if socket is not None:
        if not isinstance(socket, str) or not socket or not Path(socket).is_absolute() or '..' in Path(socket).parts or str(Path(socket)) != socket:
            raise RuntimeError('Canonical absolute private gateway socket path required')
        args += ['--microduck-socket', socket]
    return args


async def run(root):
    root=private_root(root)
    os.umask(0o077)
    begin_boot(root)
    config=json.loads((root/'service.json').read_text())
    async with ManagedPython(root,config) as python_socket:
        if python_socket:config={**config,'microduck_socket':python_socket}
        await run_runtime(root,config)


def policy_for_config(config):
    if config.get('direct_bind') is not None:
        if config.get('additional_origins'):
            raise RuntimeError('Additional public origins require a loopback proxy deployment')
        policy = Policy(config['direct_bind'], config['backend_port'], config['clients'])
        if policy.origin != config['origin']:
            raise RuntimeError('Direct listener must retain its exact browser Origin')
        return policy
    return LoopbackProxyPolicy(config['origin'], config['backend_port'],
        config.get('additional_origins', []))


async def run_runtime(root,config):
    from bridge import Bridge
    root = private_root(root)
    os.umask(0o077)
    if config.get('schema') != 1 or config.get('vm_version') != 417:
        raise RuntimeError('Unsupported managed runtime contract')
    binary, editor = selected(root, config['binary']), selected(root, config['editor'])
    if hashlib.sha256(binary.read_bytes()).hexdigest() != config['binary_sha256']:
        raise RuntimeError('Managed runtime checksum mismatch')
    data = selected(root, config['data'])
    if data.stat().st_uid != os.geteuid() or data.stat().st_mode & 0o077:
        raise RuntimeError('Managed program data must be private')
    run_dir = root / 'run'
    run_dir.mkdir(mode=0o700, exist_ok=True)
    info = data / 'pty-service.json'
    policy = policy_for_config(config)
    stopped = False
    update_restart = False
    updating = False
    server = backend = None
    log = (root / 'run/vm.log').open('ab', buffering=0)
    vm = subprocess.Popen(vm_arguments(config, binary, data, info), stdout=log, stderr=subprocess.STDOUT)
    def stop():
        nonlocal stopped
        stopped = True
        if server is not None:
            server.expire()
    def restart_for_update():
        nonlocal update_restart
        update_restart = True
        loop.call_later(.2, server.expire)
    async def quiesce():
        nonlocal updating
        if backend.owner.locked():
            raise UpdateError('Disconnect the editor before installing this native version')
        updating = True
        try:
            if vm.poll() is None:
                vm.terminate()
                try:
                    await asyncio.wait_for(asyncio.to_thread(vm.wait), 10)
                except TimeoutError:
                    vm.kill(); await asyncio.to_thread(vm.wait)
        except BaseException:
            restart_for_update()
            raise
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop)
    state = {'state': 'starting', 'origin': policy.origin, 'origins': policy.origins, 'supervisor_pid': os.getpid(),
        'vm_pid': vm.pid, 'binary_sha256': config['binary_sha256'], 'permanent': True,
        'backend': policy.bind + ':' + str(policy.port), 'vm_version': 417}
    try:
        deadline = time.monotonic() + 10
        while True:
            if vm.poll() is not None or stopped or time.monotonic() >= deadline:
                raise RuntimeError('Owned VM did not become ready')
            if info.exists():
                record = json.loads(info.read_text())
                if record.get('pid') == vm.pid:
                    break
            await asyncio.sleep(.02)
        backend = Bridge(editor, info, binary, policy.port)
        updates = BrowserUpdater(root, Path(__file__).with_name('install-smallvm-linux-arm64.sh'), quiesce,
            restart_for_update, allow_apply=config.get('allow_browser_native_install') is True)
        server = LanEditor(backend, policy, permanent=True, updates=updates)
        await server.start(activated=True)
        confirm_boot(root)
        state['state'] = 'ready'
        atomic_state(root, state)
        print(json.dumps(state), flush=True)
        async def watch():
            while vm.poll() is None or updating:
                await asyncio.sleep(.25)
            server.expire()
        watcher = asyncio.create_task(watch())
        try:
            await server.server.wait_closed()
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        if update_restart:
            raise RuntimeError('Restart managed service to activate reviewed native selection')
        if not stopped:
            raise RuntimeError('Owned VM exited; system service should restart this runtime')
    finally:
        if server is not None:
            await server.stop()
        elif backend is not None:
            backend.close()
        if vm.poll() is None:
            vm.terminate()
            try:
                vm.wait(timeout=10)
            except subprocess.TimeoutExpired:
                vm.kill(); vm.wait(timeout=5)
        log.close()
        state['state'] = 'stopped'
        atomic_state(root, state)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    args = p.parse_args()
    asyncio.run(run(args.root))
