"""Bounded Fruit Jam setup envelope; secrets are never VM code or log values."""
# SPDX-License-Identifier: MPL-2.0
import json,secrets,struct
from fruit_jam_serial import SerialVM

def wipe(data):
    for i in range(len(data)):data[i]=0

def encode_request(operation,request_id,ssid=None,key=None):
    if operation not in (1,2,3) or not 0<request_id<=0xffffffff:raise ValueError('Invalid setup operation')
    body=bytearray(b'FJNW'+bytes([1,operation])+struct.pack('<I',request_id))
    if operation==2:
        if ssid is None or key is None or not 1<=len(ssid)<=32 or not 8<=len(key)<=64 or 0 in ssid or 0 in key:
            wipe(body);raise ValueError('Invalid bounded Wi-Fi values')
        if len(key)==64 and any(c not in b'0123456789abcdefABCDEF' for c in key):
            wipe(body);raise ValueError('Invalid hexadecimal WPA key')
        body.extend((len(ssid),len(key)));body.extend(ssid);body.extend(key)
    elif ssid is not None or key is not None:
        wipe(body);raise ValueError('Unexpected setup parameters')
    try:
        packet=bytearray([251,205,0]);packet.extend(struct.pack('<H',len(body)+1));packet.extend(body);packet.append(254)
        return packet
    finally:wipe(body)

class SetupClient:
    def __init__(self,port='COM8'):
        self.vm=SerialVM(port)
        if self.vm.identity['serial']!='E46570978F1E5A34':
            self.vm.close();raise RuntimeError('Unexpected Fruit Jam USB identity')
        self.payload_written=False
    def request(self,operation,ssid=None,key=None):
        request_id=secrets.randbits(32) or 1
        packet=encode_request(operation,request_id,ssid,key)
        start=len(self.vm.events)
        try:
            self.vm.send(packet)
            if operation==2:self.payload_written=True
        finally:wipe(packet)
        def matching(event):
            if event[:2]!=(205,0) or len(event[2])>640:return False
            try:return json.loads(event[2]).get('request')==request_id
            except (ValueError,AttributeError):return False
        result=json.loads(self.vm.wait(matching,after=start)[2])
        if type(result.get('accepted')) is not bool or not isinstance(result.get('status'),dict):
            raise RuntimeError('Invalid setup response')
        return result
    def probe(self):
        result=self.request(1)
        if not result['accepted'] or result['status'].get('setup_protocol')!=1:
            raise RuntimeError('Installed Fruit Jam image lacks setup protocol 1')
        return result
    def close(self):self.vm.close()
