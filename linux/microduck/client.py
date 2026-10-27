#!/usr/bin/env python3
"""Allowlisted local gateway client; no shell execution and no automatic retry."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import sys

try:
    from .protocol import MAX_REQUEST, MAX_REPLY, RpcError, connect_checked, decode, encode, read_message, response_result
    from .gateway import validate
except ImportError:
    from protocol import MAX_REQUEST, MAX_REPLY, RpcError, connect_checked, decode, encode, read_message, response_result
    from gateway import validate


class Client:
    def __init__(self, path, owner_uid=None, timeout=10):
        self.path = Path(path)
        self.owner_uid = os.geteuid() if owner_uid is None else owner_uid
        if type(self.owner_uid) is not int or not 0 <= self.owner_uid <= 0xffffffff or not .1 <= timeout <= 60:
            raise ValueError('Invalid gateway owner UID or timeout')
        self.timeout, self.next_id, self.last_metadata = timeout, 1, None

    async def call(self, method, params=None, confirmed=False):
        request = {'jsonrpc': '2.0', 'id': self.next_id, 'method': method, 'params': {} if params is None else params, 'confirmed': confirmed}
        validate(request)
        self.next_id += 1
        self.last_metadata = None
        writer = None
        sent = False
        reply_received = False
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await connect_checked(self.path, self.owner_uid, MAX_REPLY, private_parent=True)
                payload = encode(request, MAX_REQUEST)
                sent = True
                writer.write(payload)
                await writer.drain()
                reply = await read_message(reader, MAX_REPLY)
                reply_received = True
                result = response_result(reply, request['id'], gateway_outcome=True)
                self.last_metadata = reply.get('gateway')
                return result
        except TimeoutError:
            raise RpcError(-32008, 'Gateway timeout; do not automatically retry a mutation', 'unknown' if sent else 'not_sent') from None
        except RpcError as error:
            if sent and not reply_received and error.outcome == 'not_sent':
                error.outcome = 'unknown'
            raise
        except (OSError, ValueError, ConnectionError):
            raise RpcError(-32009, 'Local gateway transport unavailable', 'unknown' if sent else 'not_sent') from None
        finally:
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

    async def health(self):
        return await self.call('robot.health')

    async def battery(self):
        health = await self.health()
        battery = health.get('battery') if isinstance(health, dict) else None
        if battery is None:
            return None  # absent means unknown, never zero volts or empty battery.
        if not isinstance(battery, dict) or any(type(battery.get(key)) not in (int, float) or not math.isfinite(battery[key]) for key in ('volts', 'percent')):
            raise RpcError(-32011, 'Robot battery reading is malformed', 'unknown')
        return {'volts': battery['volts'], 'percent': battery['percent']}

    async def quack(self, confirmed=False):
        return await self.call('robot.sound', {'tag': 'chirp'}, confirmed)

    async def perform_skill(self, name, confirmed=False):
        return await self.call('robot.do', {'skill': name}, confirmed)


async def main(args):
    request = decode(sys.stdin.buffer.readline(MAX_REQUEST + 1), MAX_REQUEST)
    validate(request)
    client = Client(args.socket, args.owner_uid)
    client.next_id = request['id']
    result = await client.call(request['method'], request.get('params', {}), request.get('confirmed', False))
    print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result, 'gateway': client.last_metadata}, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, required=True)
    parser.add_argument('--owner-uid', type=int)
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except (RpcError, ValueError, OSError) as error:
        parser.exit(1, f'MicroDuck local request failed: {error}\n')
