#!/usr/bin/env python3
"""One temporary LAN test, fresh data, stops only its own VM at lease expiry."""
# SPDX-License-Identifier: MIT
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from bridge import Bridge
from lan_editor import LanEditor, Policy


async def main():
    root = Path(__file__).resolve().parent
    binary = Path(sys.argv[1]).resolve(strict=True)
    expected = sys.argv[2]
    if hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Selected VM digest does not match reviewed evidence')
    os.umask(0o077)
    data = root / 'new-session-data'
    data.mkdir(mode=0o700, exist_ok=False)
    info = data / 'pty.json'
    with (root / 'vm.log').open('xb') as log:
        vm = subprocess.Popen([str(binary), '--data-dir', str(data), '--pty-info', str(info)], stdout=log, stderr=subprocess.STDOUT)
        backend = server = None
        try:
            deadline = time.monotonic() + 10
            while not info.exists():
                if vm.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Owned VM did not publish its discovery record')
                await asyncio.sleep(.02)
            policy = Policy('192.168.1.105', 8877, '192.168.1.0/24')
            backend = Bridge(root / 'open-editor', info, binary, 8877)
            server = LanEditor(backend, policy)
            await server.start(activated=True)
            now = time.time()
            state = {'state': 'ready', 'url': policy.origin + '/', 'supervisor_pid': os.getpid(), 'vm_pid': vm.pid,
                'binary': str(binary), 'binary_sha256': expected, 'data': str(data), 'authentication': False, 'encryption': False,
                'bind': policy.bind, 'port': policy.port, 'clients': str(policy.clients),
                'started_at': datetime.fromtimestamp(now, timezone.utc).isoformat(),
                'expires_at': datetime.fromtimestamp(now + 1800, timezone.utc).isoformat()}
            (root / 'session-state.json').write_text(json.dumps(state, indent=2) + '\n')
            print(json.dumps(state), flush=True)
            loop = asyncio.get_running_loop()
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                loop.add_signal_handler(signum, server.expire)
            async def watch_vm():
                while vm.poll() is None:
                    await asyncio.sleep(.25)
                server.expire()
            watcher = asyncio.create_task(watch_vm())
            try:
                await server.server.wait_closed()
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            state['state'] = 'stopped'
            (root / 'session-state.json').write_text(json.dumps(state, indent=2) + '\n')
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
                    vm.kill()
                    vm.wait(timeout=5)


if __name__ == '__main__':
    asyncio.run(main())
