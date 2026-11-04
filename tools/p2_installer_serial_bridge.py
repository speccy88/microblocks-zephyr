"""Guarded stdin/stdout transport for the P2 loader's physical acceptance tool.

No network server. Explicit port, exact FTDI USB serial and --allow-erase are
required. The JS acceptance tool additionally verifies P2 VM identity before
using reset/programming operations. Not used by the browser installer.
"""
# SPDX-License-Identifier: MIT
import argparse
import base64
import json
import sys
import serial
from serial.tools import list_ports


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',required=True);p.add_argument('--usb-serial',required=True);p.add_argument('--allow-erase',action='store_true')
    a=p.parse_args()
    if not a.allow_erase:raise SystemExit('Explicit --allow-erase is required')
    device=None
    try:
        for line in sys.stdin:
            request=json.loads(line);reply={'id':request['id']}
            try:
                command=request['command']
                if command=='open':
                    if device:raise RuntimeError('Port already open')
                    found=[x for x in list_ports.comports() if x.device.upper()==a.port.upper() and x.vid==0x0403 and x.serial_number==a.usb_serial]
                    if len(found)!=1:raise RuntimeError('Exact authorized FTDI port/serial not present')
                    if request['baud'] not in {115200,460800}:raise ValueError('Unsupported test baud')
                    device=serial.Serial(port=None,baudrate=request['baud'],timeout=.1,write_timeout=5)
                    device.dtr=device.rts=False;device.port=found[0].device;device.open();reply['value']=True
                elif command=='close':
                    if device:device.close();device=None
                    reply['value']=True
                elif command=='write':
                    raw=base64.b64decode(request['data'],validate=True)
                    if len(raw)>8192:raise ValueError('Bounded write exceeded')
                    if device.write(raw)!=len(raw):raise RuntimeError('Short serial write')
                    reply['value']=True
                elif command=='read':
                    device.timeout=min(max(request['timeout']/1000,.001),1)
                    raw=device.read(1)
                    if device.in_waiting:raw+=device.read(min(device.in_waiting,65535))
                    reply['value']=base64.b64encode(raw).decode('ascii')
                elif command=='clear':device.reset_input_buffer();reply['value']=True
                elif command=='signals':
                    device.rts=False;device.dtr=bool(request['dtr']);reply['value']=True
                else:raise ValueError('Unknown transport operation')
            except Exception as error:reply['error']=type(error).__name__+': '+str(error)
            print(json.dumps(reply),flush=True)
    finally:
        if device:device.close()


if __name__=='__main__':main()
