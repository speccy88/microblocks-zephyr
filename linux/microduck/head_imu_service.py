"""Explicit read-only tofd adapter; local_ipc is transport, never hardware proof."""
# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import stat

try:
    from . import head_imu_simulator as core
    from .protocol import MAX_REQUEST, decode
except ImportError:
    import head_imu_simulator as core
    from protocol import MAX_REQUEST, decode

PREFIX = 'microduck.headImu.'
METHODS = frozenset(PREFIX + name for name in ('capture', 'read', 'release'))


def validate_source(config, daemon='tofd'):
    if daemon not in ('tofd','padd') or not isinstance(config, dict) or set(config) != {'version', 'daemon', 'path', 'uid'} \
            or type(config['version']) is not int or config['version'] != 1 or config['daemon'] != daemon \
            or not isinstance(config['path'], str) or not config['path'].startswith('/') \
            or '\x00' in config['path'] or len(config['path'].encode('utf-8')) > 103 \
            or not core.wire.integer(config['uid'], 0, 0xffffffff):
        raise ValueError('Reader config requires version1, the selected daemon, absolute socket path and expected numeric UID')
    return dict(config)


def load_source(path, daemon='tofd'):
    path = Path(path)
    if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
        raise ValueError('Canonical absolute reader config path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > MAX_REQUEST:
            raise ValueError('Reader config must be bounded, private and owned by this user')
        return validate_source(decode(os.read(fd, MAX_REQUEST + 1).rstrip(b'\n') + b'\n', MAX_REQUEST), daemon)
    finally:
        os.close(fd)


def validate(request):
    core.require(isinstance(request, dict) and isinstance(request.get('method'), str) and request['method'] in METHODS, -32601)
    return core.validate({**request, 'method': core.PREFIX + request['method'].removeprefix(PREFIX)})


def result(kind, status, **parts):
    return {'origin': 'local_ipc', 'source': 'tofd', 'physical_hardware_verified': False,
            'physical_movement_enabled': False, 'kind': kind, 'status': status, **parts}


class ServiceStore(core.HeadStore):
    def __init__(self, config):
        self.config = validate_source(config)
        super().__init__(Path(self.config['path']).parent)

    def envelope(self, kind, status, **parts):
        return result(kind, status, **parts)

    async def read_source(self):
        return await core.read_tofd_head(Path(self.config['path']), self.config['uid'])

    async def dispatch(self, request):
        name, p = validate(request)
        value = await self.acquire() if name == 'capture' else self.release(p['handle']) if name == 'release' else self.read(p['handle'], p['field'], p['component'])
        core.encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': value}, 760)
        return value
