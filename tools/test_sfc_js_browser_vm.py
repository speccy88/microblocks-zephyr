#!/usr/bin/env python3
"""Owned Linux session for actual browser SFC tests; loopback only."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['binary','editor','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--browser');a=p.parse_args()
    if sys.platform!='linux' or os.geteuid()==0:raise RuntimeError('Requires unprivileged Linux')
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='sfc-js-browser-vm-') as temp:
        with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
        child=subprocess.Popen([sys.executable,str(root/'linux/arm64/session.py'),'--binary',str(a.binary.resolve()),
            '--editor',str(a.editor.resolve()),'--data',str(Path(temp)/'data'),'--port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            if not select.select([child.stdout],[],[],20)[0]:raise RuntimeError('VM session readiness deadline')
            line=child.stdout.readline()
            if not line:raise RuntimeError(child.stderr.read())
            assert json.loads(line)['state']=='ready'
            cmd=[sys.executable,str(root/'tests/sfc_js_browser.py'),'--url',f'http://127.0.0.1:{port}/','--output',str(a.output)]
            if a.browser:cmd+=['--browser',a.browser]
            subprocess.run(cmd,check=True,timeout=180)
        finally:
            if child.poll() is None:child.terminate()
            child.communicate(timeout=15)
            if child.returncode:raise RuntimeError('VM supervisor did not exit cleanly')


if __name__=='__main__':main()
