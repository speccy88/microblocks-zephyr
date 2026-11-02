#!/usr/bin/env python3
"""One isolated, persistent trusted plugin. Protocol uses bounded UTF-8 JSON."""
# SPDX-License-Identifier: MIT
import importlib
import json
from pathlib import Path
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    __package__='linux.extensions'
from .api import Context,ExtensionError,MAX_REQUEST,bounded_json,failure


def run():
    output=sys.stdout.buffer
    sys.stdout=sys.stderr # plugin prints must never corrupt the protocol
    first=sys.stdin.buffer.readline(MAX_REQUEST+1)
    config=json.loads(first);plugin=None
    try:
        module,factory=config['factory'].split(':')
        plugin=getattr(importlib.import_module(module),factory)(config['settings'],Context(Path(config['state']),config['board']))
        operations=plugin.operations
        if not isinstance(operations,dict) or any(not isinstance(k,str) or not callable(v) for k,v in operations.items()):raise ExtensionError('configuration','Invalid extension operation registry')
        output.write(b'{"ready":true}\n');output.flush()
    except BaseException as error:
        output.write(bounded_json(failure(error))+b'\n');output.flush();return
    try:
        for line in iter(lambda:sys.stdin.buffer.readline(MAX_REQUEST+1),b''):
            if len(line)>MAX_REQUEST:break
            request=json.loads(line)
            try:
                operation=operations.get(request['method'])
                if not operation:raise ExtensionError('operation_missing','This operation is not provided by the configured Python extension')
                result={'ok':True,'value':operation(request['args'])}
                raw=bounded_json(result)
            except BaseException as error:raw=bounded_json(failure(error))
            output.write(raw+b'\n');output.flush()
    finally:
        if callable(getattr(plugin,'close',None)):plugin.close()


if __name__=='__main__':run()
