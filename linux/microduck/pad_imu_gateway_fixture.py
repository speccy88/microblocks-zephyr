#!/usr/bin/env python3
"""SIMULATION input through the normal read-only gateway; private Unix lab only."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import stat
import sys

try:
    from .gateway import Gateway, load_config
    from .pad_imu_service import load_source
    from .pad_imu_simulator import ImuSimulator, PROFILES
    from .simulator import _fresh_file
except ImportError:
    from gateway import Gateway, load_config
    from pad_imu_service import load_source
    from pad_imu_simulator import ImuSimulator, PROFILES
    from simulator import _fresh_file


class GatewayFixture:
    def __init__(self, directory, profile='normal'):
        self.directory, self.profile = Path(directory), profile
        self.source = self.gateway = None

    async def start(self):
        root = self.directory
        if not root.is_absolute() or root.parent.resolve(strict=True) != root.parent or self.profile not in PROFILES:
            raise ValueError('Canonical new private fixture directory and known profile required')
        root.mkdir(mode=0o700)
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Fixture directory must be private and current-user-owned')
        try:
            self.source = ImuSimulator(root/'source', self.profile)
            await self.source.start()
            local = root/'normal'
            local.mkdir(mode=0o700)
            _fresh_file(local/'gateway.json', {'version':1,'upstreams':{}})
            _fresh_file(local/'pad-imu.json', {'version':1,'daemon':'padd','path':str(root/'source/pad.sock'),'uid':os.geteuid()})
            self.gateway = Gateway(load_config(local/'gateway.json'), pad_imu=load_source(local/'pad-imu.json'))
            await self.gateway.start(local/'gateway.sock')
            ready = {'simulation':True,'data_source':'fixed fictional padd IMU; no device or physical robot',
                'normal_gateway':True,'gateway_socket':str(local/'gateway.sock'),'profile':self.profile,
                'physical_hardware_verified':False,'physical_movement_enabled':False,
                'reading_origin':'local_ipc describes transport only; all input in this fixture is simulated',
                'library':'MicroDuck + Pad_IMU','example':'pad-imu.ubp'}
            _fresh_file(root/'gateway-fixture.json', ready)
            return ready
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        if self.gateway:
            await self.gateway.stop()
        if self.source:
            await self.source.stop()


async def main(args):
    fixture, stopped = GatewayFixture(args.directory, args.fixture), asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopped.set)
    try:
        print(json.dumps(await fixture.start()), flush=True)
        await stopped.wait()
    finally:
        await fixture.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--fixture', choices=PROFILES, default='normal')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux private Unix sockets required')
    asyncio.run(main(args))
