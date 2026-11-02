"""Pure framing for opt-in, leased P4 serial-rate negotiation."""
# SPDX-License-Identifier: MIT
import struct

def rate_packet(operation,token=0,baud=0):
    if operation not in range(5) or not 0<=token<=0xffffffff:raise ValueError('Invalid serial operation/token')
    if operation==0:
        if baud:raise ValueError('Capability query has no target baud')
    elif not token or baud not in ((460800,921600) if operation==1 else ((115200,) if operation==3 else (460800,921600))):
        raise ValueError('Invalid serial rate/token')
    body=struct.pack('<4sBBBBII',b'P4BR',1,operation,0,0,token,baud)
    return bytes((251,214,0,17,0))+body+b'\xfe'

def rate_reply(body,operation,token):
    if len(body)!=16:raise ValueError('Truncated serial-rate reply')
    magic,version,op,status,state,nonce,baud=struct.unpack('<4sBBBBII',body)
    if magic!=b'P4BR' or version!=1 or op!=operation or nonce!=token or status>3 or state>3 or baud not in (115200,460800,921600):raise ValueError('Invalid serial-rate reply')
    return status,state,baud
