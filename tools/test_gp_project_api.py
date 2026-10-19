#!/usr/bin/env python3
"""Headless check of packaged GP project serialization; no browser or hardware.

Uses a supplied native GP interpreter with the *packaged* GP 2.5.8 sources.
Only the browser editor lookup and response sink are substituted. No window
is opened, and no serial API is called. This is not Web Serial acceptance.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PROBE = """
to findMicroBlocksEditor { return (global 'testEditor') }
to browserRespondAPIRequest id response { setGlobal 'testResponse' response }

to startup {
    setGlobal 'scale' 1
    setGlobal 'blockScale' 1
    initMicroBlocksSpecs (new 'SmallCompiler')
    project = (newMicroBlocksProject)
    data = (join 'module main' (newline) (readFile '../fixture.ubl'))
    loadFromString project data false
    scripter = (new 'MicroBlocksScripter')
    setField scripter 'mbProject' project
    pane = (newScriptEditor 100 100)
    frame = (new 'ScrollFrame')
    setField frame 'contents' pane
    setField scripter 'scriptsFrame' frame
    editor = (new 'MicroBlocksEditor')
    setField editor 'scripter' scripter
    setGlobal 'testEditor' editor
    api = (api (smallRuntime scripter))
    dispatchCall api (array 1 'portal.serialize' '[]')
    response = (global 'testResponse')
    if (isNil response) { error 'no serialization response' }
    writeFile '../response.json' response
    second = (newMicroBlocksProject)
    loadFromString second (jsonParse response) false
    writeFile '../roundtrip.json' (jsonStringify (codeString second))
    exit
}
"""


def check(gp, editor, output):
    root = Path(__file__).resolve().parents[1]
    editor = editor.resolve()
    gp = gp.resolve()
    js = (editor/'gp_wasm.js').read_bytes()
    data = (editor/'gp_wasm.data').read_bytes()
    match = re.search(rb'loadPackage\((\{"files":\[.*?\],"remote_package_size":\d+\})\)', js)
    if not match:
        raise ValueError('Build the patched portal before running the GP source check')
    metadata = json.loads(match[1])
    if metadata['remote_package_size'] != len(data):
        raise ValueError('Packaged GP data length differs')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gp-api-', dir=output.resolve()) as scratch:
        work = Path(scratch)
        runtime = work/'gp'
        runtime.mkdir()
        translations = work/'translations'
        translations.mkdir()
        for name in ('en.po', 'locales.json'):
            shutil.copyfile(editor/'translations'/name, translations/name)
        libraries = []
        for item in metadata['files']:
            name = item['filename']
            if not name.startswith('/runtime/lib/') or not name.endswith('.gp'):
                continue
            if Path(name).name != name.removeprefix('/runtime/lib/'):
                raise ValueError('Unexpected GP library path')
            start, end = item['start'], item['end']
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start <= end <= len(data):
                raise ValueError('Invalid GP source range')
            target = runtime/Path(name).name
            target.write_bytes(data[start:end])
            libraries.append(str(target))
        if not libraries:
            raise ValueError('No packaged GP sources')
        shutil.copyfile(root/'boards/propeller2/integration/P2_Hardware.ubl', work/'fixture.ubl')
        probe = work/'probe.gp'
        probe.write_text(PROBE, encoding='utf-8', newline='\n')
        result = subprocess.run([str(gp), *sorted(libraries), str(probe), '-'], cwd=runtime,
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
        (output/'gp-project-api.log').write_bytes(result.stdout+result.stderr)
        # GP can return zero after a script error and EOF at its debug prompt.
        # Require the actual response artifacts and matching serialized data.
        first = json.loads((work/'response.json').read_text(encoding='utf-8'))
        second = json.loads((work/'roundtrip.json').read_text(encoding='utf-8'))
        if result.returncode or first != second or "module 'P2 Hardware'" not in first:
            raise RuntimeError('Packaged GP serialization/roundtrip failed')
        (output/'gp-project-response.ubp').write_text(first, encoding='utf-8', newline='\n')
    report = dict(result='PASS', tested_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='headless packaged GP source API; browser response sink substituted',
                  gp_executable_sha256=hashlib.sha256(gp.read_bytes()).hexdigest(),
                  gp_data_sha256=hashlib.sha256(data).hexdigest(),
                  project_bytes=len(first.encode('utf-8')), roundtrip_equal=True,
                  graphical_browser_test=False, web_serial_test=False)
    (output/'gp-project-api.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gp', required=True, type=Path)
    parser.add_argument('--editor', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.gp, args.editor, args.output), indent=2))
