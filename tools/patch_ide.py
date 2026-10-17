#!/usr/bin/env python3
"""Repack the pinned GP filesystem with Waveshare library and example controls.

The editor, interpreter and compiler remain the real MicroBlocks/GP binaries.
Only its existing source-level UNO Q integration endpoints and library change.
"""
# SPDX-License-Identifier: MPL-2.0
import json
import re


def patch_ide(javascript: bytes, data: bytes, library: bytes):
    source = javascript.decode('utf-8')
    match = re.search(r'loadPackage\((\{files:\[.*?\],remote_package_size:\d+\})\)', source)
    if not match:
        raise ValueError('Unexpected pinned Emscripten package metadata')
    metadata = json.loads(re.sub(r'([,{])(\w+):', r'\1"\2":', match[1]))
    if metadata['remote_package_size'] != len(data):
        raise ValueError('GP package length mismatch')
    packed = bytearray()
    files = []
    api_count = library_count = 0
    for entry in metadata['files']:
        name = entry['filename']
        start_offset, end_offset = int(entry['start']), int(entry['end'])
        if start_offset != entry['start'] or end_offset != entry['end'] or not 0 <= start_offset <= end_offset <= len(data):
            raise ValueError('Invalid embedded GP file range')
        payload = data[start_offset:end_offset]
        if b"endPoint == 'unoq.loadLibrary'" in payload:
            api_count += 1
            payload = payload.replace(b"'unoq.loadLibrary'", b"'rlcd.loadLibrary'")
            payload = payload.replace(b"'unoq.openExample'", b"'rlcd.openExample'")
            payload = payload.replace(b'Libraries/UNO_Q_Hardware.ubl', b'Libraries/Waveshare_RLCD_4_2.ubl')
            payload = payload.replace(b"'UNO Q Hardware'", b"'Waveshare RLCD 4.2'")
            payload = payload.replace(b"'Examples/UNO Q/'", b"'Examples/Waveshare/'")
            payload = payload.replace(b"'arithmetic' 'output' 'rgb' 'matrix' 'combined' 'matrix-drawing'", b"'arithmetic' 'output'")
        if name == '/Libraries/UNO_Q_Hardware.ubl':
            name = '/Libraries/Waveshare_RLCD_4_2.ubl'; payload = library; library_count += 1
        if name.startswith('/Examples/UNO Q/'):
            if name.rsplit('/', 1)[-1] not in ('arithmetic.ubp', 'output.ubp'):
                continue
            name = name.replace('/Examples/UNO Q/', '/Examples/Waveshare/')
        start = len(packed); packed.extend(payload)
        files.append({'filename': name, 'start': start, 'end': len(packed)})
    if api_count != 1 or library_count != 1:
        raise ValueError('Expected exactly one GP API source and one board library')
    metadata = {'files': files, 'remote_package_size': len(packed)}
    source = source[:match.start(1)] + json.dumps(metadata, separators=(',', ':')) + source[match.end(1):]
    source = source.replace('"/Examples","UNO Q"', '"/Examples","Waveshare"')
    return source.encode('utf-8'), bytes(packed)
