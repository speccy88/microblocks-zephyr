#!/usr/bin/env python3
"""Binary SmallVM transport for the positively identified Fruit Jam USB CDC.

No firmware flashing or serial reset. COM4/COM5 and the Pico UART are excluded.
"""
# SPDX-License-Identifier: MPL-2.0
import struct
import time
import zlib
import serial
from serial.tools import list_ports
from test_wireless_vm import VM


def fruit_jam_ports():
    return [p for p in list_ports.comports()
            if p.vid == 0x2fe3 and p.pid == 0x0004
            and p.device.upper() not in ('COM4', 'COM5', 'COM7')]


class SerialVM(VM):
    def __init__(self, port=None):
        candidates = fruit_jam_ports()
        if port:
            candidates = [p for p in candidates if p.device.upper() == port.upper()]
        if len(candidates) != 1:
            raise RuntimeError('Expected exactly one Fruit Jam Zephyr CDC: '+repr(
                [(p.device,p.vid,p.pid,p.serial_number) for p in candidates]))
        self.identity = dict(port=candidates[0].device, vid=candidates[0].vid,
            pid=candidates[0].pid, serial=candidates[0].serial_number,
            product=candidates[0].product, location=candidates[0].location)
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=.1,
                                    write_timeout=3)
        self.serial.port = candidates[0].device
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.open()
        self.serial.dtr = True
        self.buffer = bytearray()
        self.events = []
        self.last_ping = 0
        self.received_bytes = 0
        self.sent_bytes = 0
        self.host = candidates[0].device

    def send(self, data):
        if self.serial.write(data) != len(data):
            raise RuntimeError('Short serial write')
        self.sent_bytes += len(data)

    def short(self, kind, index=0):
        self.send(bytes([250,kind,index]))

    def pump(self):
        if time.monotonic()-self.last_ping > .5:
            self.short(26,73)
            self.last_ping = time.monotonic()
        data = self.serial.read(min(4096,self.serial.in_waiting or 1))
        self.received_bytes += len(data)
        self.buffer.extend(data)
        if len(self.buffer) > 8192:
            raise RuntimeError('Unbounded protocol buffer')
        while self.buffer:
            if self.buffer[0] == 250:
                if len(self.buffer) < 3:return
                self.events.append((self.buffer[1],self.buffer[2],b''))
                del self.buffer[:3]
            elif self.buffer[0] == 251:
                if len(self.buffer) < 5:return
                size = int.from_bytes(self.buffer[3:5],'little')
                if size > 4096:raise RuntimeError('Invalid VM message length')
                if len(self.buffer) < 5+size:return
                self.events.append((self.buffer[1],self.buffer[2],bytes(self.buffer[5:5+size])))
                del self.buffer[:5+size]
            else:raise RuntimeError('Unframed USB VM output: '+self.buffer[:32].hex())

    def upload(self, chunk, code, kind=1, fragmented=False):
        if len(code)%4:raise ValueError('Bytecode must contain complete words')
        body = bytes([kind])+code+b'\xfe'
        packet = bytes([251,32,chunk])+struct.pack('<H',len(body))+body
        start = len(self.events)
        if fragmented:
            for pos in range(0,len(packet),37):
                self.send(packet[pos:pos+37])
                time.sleep(.003)
        else:self.send(packet)
        actual = int.from_bytes(self.wait(lambda e:e[:2]==(23,chunk),after=start)[2],'little')
        if actual != zlib.crc32(code):raise AssertionError('Uploaded code CRC mismatch')
        return actual

    def close(self):
        self.serial.close()
