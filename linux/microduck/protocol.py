"""Bounded JSON-RPC and verified Unix peer transport; standard library only."""
# SPDX-License-Identifier: MIT
import asyncio
import json
import math
import os
from pathlib import Path
import socket
import stat
import struct

API_VERSION = 44
SOURCE_COMMIT = '96b89d8613f06722c1d64ce75ab0d7124fed9d8f'
MAX_REQUEST = 8192
MAX_REPLY = 65536


class RpcError(Exception):
    def __init__(self, code, message, outcome='not_sent'):
        super().__init__(message)
        self.code, self.message, self.outcome = code, message, outcome


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RpcError(-32600, 'Duplicate JSON object member')
        result[key] = value
    return result


def decode(line, limit):
    if not line or len(line) > limit or not line.endswith(b'\n'):
        raise RpcError(-32600, 'Bounded newline-delimited JSON required')
    try:
        value = json.loads(line, object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
        pending = [(value, 0)]
        count = 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 24 or count > 8192 or isinstance(item, float) and not math.isfinite(item):
                raise ValueError('JSON value bounds')
            if isinstance(item, dict):
                pending.extend((part, depth + 1) for part in item.values())
            elif isinstance(item, list):
                pending.extend((part, depth + 1) for part in item)
        return value
    except RpcError:
        raise
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise RpcError(-32700, 'Invalid bounded JSON') from None


def encode(value, limit):
    try:
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise RpcError(-32600, 'Value cannot be encoded as bounded JSON') from None
    if len(data) > limit:
        raise RpcError(-32010, 'JSON-RPC message exceeds byte limit')
    return data


def peer_uid(sock):
    try:
        pid, uid, gid = struct.unpack('iII', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('iII')))
        if pid <= 0:
            raise ValueError('pid')
        return uid
    except (OSError, ValueError, struct.error, AttributeError):
        raise RpcError(-32001, 'Unix peer credentials unavailable') from None


def socket_identity(path, expected_uid, private_parent=False):
    path = Path(path)
    if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
        raise RpcError(-32001, 'Canonical absolute Unix socket path required')
    parent = path.parent.stat()
    if parent.st_uid not in (0, expected_uid, os.geteuid()) or parent.st_mode & (0o077 if private_parent else 0o022):
        raise RpcError(-32001, 'Unix socket parent permissions are not trusted')
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != expected_uid or info.st_mode & 0o007:
        raise RpcError(-32001, 'Unix socket owner, mode or file type is not trusted')
    return info.st_dev, info.st_ino


async def connect_checked(path, expected_uid, limit, private_parent=False):
    identity = socket_identity(path, expected_uid, private_parent)
    reader, writer = await asyncio.open_unix_connection(str(path), limit=limit)
    try:
        if peer_uid(writer.get_extra_info('socket')) != expected_uid or socket_identity(path, expected_uid, private_parent) != identity:
            raise RpcError(-32001, 'Unix server peer does not match the configured owner')
        return reader, writer
    except BaseException:
        writer.close()
        await writer.wait_closed()
        raise


async def read_message(reader, limit):
    try:
        line = await reader.readline()
    except (ValueError, asyncio.LimitOverrunError):
        raise RpcError(-32010, 'JSON-RPC line exceeds byte limit') from None
    return decode(line, limit)


def response_result(reply, expected_id, gateway_outcome=False):
    unavailable = gateway_outcome and isinstance(reply, dict) and reply.get('id') is None and isinstance(reply.get('error'), dict) and isinstance(reply['error'].get('data'), dict) and reply['error']['data'].get('outcome') == 'not_sent'
    if not isinstance(reply, dict) or reply.get('jsonrpc') != '2.0' or not unavailable and (type(reply.get('id')) is not int or reply['id'] != expected_id):
        raise RpcError(-32011, 'Upstream response ID or envelope mismatch', 'unknown')
    if ('result' in reply) == ('error' in reply):
        raise RpcError(-32011, 'Upstream response must contain result or error', 'unknown')
    if 'error' in reply:
        error = reply['error']
        if not isinstance(error, dict) or type(error.get('code')) is not int:
            raise RpcError(-32011, 'Invalid upstream error envelope', 'unknown')
        # Do not copy arbitrary remote error text/data into logs or replies.
        outcome = 'rejected'
        if gateway_outcome and isinstance(error.get('data'), dict) and error['data'].get('outcome') in ('not_sent', 'unknown', 'rejected'):
            outcome = error['data']['outcome']
        raise RpcError(error['code'], 'Local gateway or robot service refused the request', outcome)
    return reply['result']


class Upstream:
    def __init__(self, path, uid, timeout=3):
        if not isinstance(path, (str, Path)) or not Path(path).is_absolute() or type(uid) is not int or not 0 <= uid <= 0xffffffff or not .05 <= timeout <= 15:
            raise ValueError('Invalid upstream UID or timeout')
        self.path, self.uid, self.timeout = Path(path), uid, timeout

    async def call(self, method, params, request_id):
        sent = False
        writer = None
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await connect_checked(self.path, self.uid, MAX_REPLY)
                writer.write(encode({'jsonrpc': '2.0', 'id': 0, 'method': 'hello', 'params': {'api_version': API_VERSION}}, MAX_REQUEST))
                await writer.drain()
                hello = response_result(await read_message(reader, MAX_REPLY), 0)
                if not isinstance(hello, dict) or type(hello.get('api_version')) is not int:
                    raise RpcError(-32011, 'Upstream hello did not report an API version')
                if method == 'hello':
                    return hello, hello['api_version']
                payload = encode({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}, MAX_REQUEST)
                sent = True
                writer.write(payload)
                await writer.drain()
                result = response_result(await read_message(reader, MAX_REPLY), request_id)
                return result, hello['api_version']
        except TimeoutError:
            raise RpcError(-32008, 'Robot service timed out; no automatic retry', 'unknown' if sent else 'not_sent') from None
        except RpcError as error:
            if sent and error.outcome == 'not_sent':
                error.outcome = 'unknown'
            raise
        except (OSError, ValueError, ConnectionError):
            raise RpcError(-32009, 'Robot service transport unavailable', 'unknown' if sent else 'not_sent') from None
        finally:
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass
