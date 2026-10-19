#!/usr/bin/env python3
"""Exact-device binary P2 transport. Requires pyserial==3.5, websocket-client==1.9.0.

No enumeration opens other ports. DTR/RTS stay deasserted. Construction checks
the exact observed USB serial and the installed firmware's module identity.
"""
# SPDX-License-Identifier: MPL-2.0
import struct
import time
import zlib
import serial
from serial.tools import list_ports
from test_wireless_vm import VM, op, words

BOARDS = {'eval': 'Parallax P2 Eval Rev C', 'edge': 'Parallax P2 Edge',
          'edge32': 'Parallax P2 Edge 32MB'}


class P2SerialVM(VM):
    def __init__(self, port, usb_serial, board):
        candidates = [p for p in list_ports.comports() if p.device.upper() == port.upper()
                      and p.vid == 0x0403 and p.serial_number == usb_serial]
        if len(candidates) != 1:
            raise RuntimeError('Exact P2 FTDI port/serial not present')
        item = candidates[0]
        self.identity = dict(port=item.device, vid=item.vid, pid=item.pid, serial=item.serial_number)
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=.05, write_timeout=3)
        self.serial.port = item.device
        self.serial.dtr = self.serial.rts = False
        self.serial.open()
        self.host = item.device
        self.buffer = bytearray(); self.events = []; self.last_ping = 0
        self.received_bytes = self.sent_bytes = 0
        self.upload_seconds = []
        try:
            # A successful single-stage download can return while its RAM
            # flasher is still programming. Retry the identity request rather
            # than losing the only request before the VM starts.
            body = None
            for attempt in range(12):
                start = len(self.events); self.short(12)
                try:
                    body = self.wait(lambda e: e[:2] == (22, 0), seconds=1, after=start)[2]
                    break
                except TimeoutError:
                    pass
            if body is None:
                raise TimeoutError('P2 VM did not answer version within 12 seconds')
            self.version = body[1:].decode('utf-8')
            if not self.version.endswith(BOARDS[board]):
                raise RuntimeError('Firmware/module mismatch: '+self.version)
        except BaseException:
            self.close(); raise

    def send(self, data):
        if self.serial.write(data) != len(data):
            raise RuntimeError('Short P2 serial write')
        self.sent_bytes += len(data)

    def short(self, kind, index=0):
        self.send(bytes([250, kind, index]))

    def pump(self):
        if time.monotonic()-self.last_ping > .5:
            self.short(26, 73); self.last_ping = time.monotonic()
        data = self.serial.read(min(4096, self.serial.in_waiting or 1))
        self.received_bytes += len(data); self.buffer.extend(data)
        if len(self.buffer) > 8192:
            raise RuntimeError('P2 input buffer limit exceeded')
        while self.buffer:
            if self.buffer[0] == 250:
                if len(self.buffer) < 3: return
                self.events.append((self.buffer[1], self.buffer[2], b'')); del self.buffer[:3]
            elif self.buffer[0] == 251:
                if len(self.buffer) < 5: return
                size = int.from_bytes(self.buffer[3:5], 'little')
                if size > 4096: raise RuntimeError('Invalid P2 VM frame length')
                if len(self.buffer) < 5+size: return
                self.events.append((self.buffer[1], self.buffer[2], bytes(self.buffer[5:5+size])))
                del self.buffer[:5+size]
            else:
                raise RuntimeError('Unframed P2 output: '+self.buffer[:20].hex())

    def upload(self, chunk, code, kind=1, fragmented=False):
        if len(code) % 4: raise ValueError('Code must contain complete storage words')
        body = bytes([kind])+code+b'\xfe'
        packet = bytes([251, 32, chunk])+struct.pack('<H', len(body))+body
        start = len(self.events); began = time.monotonic()
        if fragmented:
            for pos in range(0, len(packet), 37):
                self.send(packet[pos:pos+37]); time.sleep(.003)
        else: self.send(packet)
        actual = int.from_bytes(self.wait(lambda e: e[:2] == (23, chunk), seconds=10, after=start)[2], 'little')
        self.upload_seconds.append(time.monotonic()-began)
        if actual != zlib.crc32(code): raise AssertionError('P2 code CRC mismatch')
        return actual

    def all_crcs(self):
        start = len(self.events); self.short(38, 1)
        body = self.wait(lambda e: e[:2] == (39, 0), after=start)[2]
        if len(body) % 5: raise RuntimeError('Invalid CRC table')
        return {body[i]: int.from_bytes(body[i+1:i+5], 'little') for i in range(0, len(body), 5)}

    def close(self):
        self.serial.close()


def primitive(name, arguments=()):
    """Encode real 16-bit SmallVM IOPrims calls, including string literals."""
    ops = [op(9)]; literals = []
    def string_literal(text, reference, primitive_name=False):
        raw = text.encode('utf-8')+b'\0'; raw += b'\0'*(-len(raw) % 4)
        literals.append((reference, struct.pack('<I', (len(raw)//4 << 4) | 4)+raw, primitive_name))
    for value in arguments:
        if isinstance(value, str):
            ops.extend([op(5), 0]); string_literal(value, len(ops)-1)
        elif isinstance(value, bool): ops.append(op(2, 4 if value else 0))
        elif -64 <= value <= 63: ops.append(op(2, 2*value+1))
        elif -4194304 <= value <= 4194303:
            tagged = 2*value+1; ops.extend([op(3, tagged & 255), tagged >> 8 & 65535])
        else: raise ValueError('Argument outside test encoder range')
    ops.extend([op(37, len(arguments)), 0, op(35), op(127)])
    string_literal(name, len(ops)-3, True)
    if len(ops) % 2: ops.append(0)
    out = bytearray(words(ops))
    for reference, literal, primitive_name in literals:
        offset = len(out)//2-reference
        if primitive_name: offset += 3 << 10
        struct.pack_into('<H', out, reference*2, offset)
        out.extend(literal)
    return bytes(out)
