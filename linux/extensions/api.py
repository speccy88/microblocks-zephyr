"""Small plugin contract; wire input never chooses executable Python code."""
# SPDX-License-Identifier: MIT
from dataclasses import dataclass
import json
import math
from pathlib import Path

MAX_REQUEST=8192
MAX_REPLY=60000


class ExtensionError(Exception):
    def __init__(self,code,message,outcome='rejected'):
        super().__init__(message);self.code=code;self.message=message;self.outcome=outcome


@dataclass(frozen=True)
class Context:
    state: Path
    board: str


def bounded_json(value,limit=MAX_REPLY):
    pending=[(value,0)];count=0
    while pending:
        v,depth=pending.pop();count+=1
        if depth>16 or count>8192:raise ExtensionError('result_limit','Python result exceeds its structure limit')
        if isinstance(v,dict):
            if len(v)>256 or any(type(k) is not str for k in v):raise ExtensionError('result_type','Python objects require bounded string keys')
            pending.extend((x,depth+1) for x in v.values())
        elif isinstance(v,(list,tuple)):pending.extend((x,depth+1) for x in v)
        elif v is not None and type(v) not in (str,int,float,bool):raise ExtensionError('result_type','Python operation returned an unsupported value')
        elif isinstance(v,float) and not math.isfinite(v):raise ExtensionError('result_type','Nonfinite Python values are unsupported')
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if len(raw)>limit:raise ExtensionError('result_limit','Python result exceeds its byte limit')
    return raw


def arguments(value,allowed,required=()):
    if not isinstance(value,dict) or set(value)-set(allowed) or set(required)-set(value):raise ExtensionError('arguments','Missing or unknown operation arguments')
    return value


def text(value,maximum,label):
    if type(value) is not str or len(value.encode('utf-8'))>maximum:raise ExtensionError('arguments',label+' must be bounded text')
    return value


def failure(error):
    if isinstance(error,ExtensionError):return {'ok':False,'error':{'code':error.code,'message':error.message,'outcome':error.outcome}}
    if isinstance(error,ModuleNotFoundError):return {'ok':False,'error':{'code':'dependency_missing','message':'Python extension dependency is missing; install its documented official package in the configured environment','outcome':'rejected'}}
    return {'ok':False,'error':{'code':'operation_failed','message':'Python extension failed; check its configuration and device availability','outcome':'unknown'}}
