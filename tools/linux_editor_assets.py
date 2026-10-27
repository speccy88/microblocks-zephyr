#!/usr/bin/env python3
"""Strictly adapt the pinned real GP 2.5.8 filesystem to Linux core runtime.

linux_package(javascript, data) includes the browser project serialize/load API;
callers must not inject that API a second time. No hardware library is claimed.
"""
# SPDX-License-Identifier: MPL-2.0
import json
from pathlib import Path, PurePosixPath
import re

LINUX_LIBRARY = b"""module 'Linux Core' Output
author 'MicroBlocks Linux ARM64 port'
version 1 0
description 'Core SmallVM language and runtime only. This library adds no GPIO, robot actuators, sensors or media primitives.'
"""

PROJECT_API = b"""} (endPoint == 'portal.serialize') {
        saveScripts scripter nil true
        respondAPIRequest this id (codeString (project scripter))
    } (endPoint == 'portal.load') {
        respondAPIRequest this id 0
        openProject editor (at params 1) (at params 2)
    """


def replace_once(payload, before, after):
    if payload.count(before) != 1:
        raise ValueError('Unexpected pinned Linux editor patch anchor: ' + repr(before[:90]))
    return payload.replace(before, after, 1)


def package_metadata(javascript, data, *, pinned=False):
    source = javascript.decode('utf-8')
    pattern = (r'loadPackage\((\{files:\[.*?\],remote_package_size:\d+\})\)' if pinned else
               r'loadPackage\((\{(?:files|"files"):\[.*?\],(?:remote_package_size|"remote_package_size"):\d+\})\)')
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise ValueError('Expected one pinned GP filesystem package')
    match = matches[0]
    metadata = json.loads(re.sub(r'([,{])(\w+):', r'\1"\2":', match[1]))
    if metadata.get('remote_package_size') != len(data) or not isinstance(metadata.get('files'), list):
        raise ValueError('GP package size or file table differs')
    names = set()
    cursor = 0
    for item in metadata['files']:
        name = item.get('filename')
        if not isinstance(name, str) or not name.startswith('/') or '..' in PurePosixPath(name).parts or name in names:
            raise ValueError('Unsafe or duplicate GP filesystem path')
        names.add(name)
        start, end = item.get('start'), item.get('end')
        if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ValueError('Invalid GP file range type')
        if int(start) != start or int(end) != end or start != cursor or not 0 <= start <= end <= len(data):
            raise ValueError('GP filesystem ranges must cover the package exactly once')
        cursor = int(end)
    if cursor != len(data):
        raise ValueError('Unaccounted GP filesystem bytes')
    return source, match, metadata


def unpack_package(javascript, data):
    """Return checked virtual filenames/payloads for focused acceptance tests."""
    _, _, metadata = package_metadata(javascript, data)
    return {item['filename']: data[int(item['start']):int(item['end'])] for item in metadata['files']}


def linux_package(javascript: bytes, data: bytes, *, microduck=False, repo=None):
    """Repack only the known UNO Q customization, preserving the real GP engine.

    The compiler uses the existing IO primitive index under alias ``linux``.
    The Linux Core module has no blocks. Only arithmetic and bounded output
    examples survive the old UNO Q example namespace. Project APIs match the
    previously accepted multi-board portal serialization/load implementation.
    """
    source, match, metadata = package_metadata(javascript, data, pinned=True)
    if type(microduck) is not bool:
        raise ValueError('MicroDuck library selection must be explicit')
    library = example = motion_library = motion_example = sensor_library = sensor_example = robot_library = telemetry_library = robot_example = media_library = media_example = imu_library = imu_example = head_library = head_example = head_service_library = head_service_example = depth_library = depth_example = gamepad_library = gamepad_example = None
    if microduck:
        root = Path(repo) if repo is not None else Path(__file__).resolve().parents[1]
        library = (root / 'linux/microduck/MicroDuck.ubl').read_bytes()
        example = (root / 'linux/microduck/health.ubp').read_bytes() + b'\n' + library
        motion_library = (root / 'linux/microduck/Motion_Simulation.ubl').read_bytes()
        motion_example = (root / 'linux/microduck/motion-simulation.ubp').read_bytes() + b'\n' + library + b'\n' + motion_library
        sensor_library = (root / 'linux/microduck/Sensor_Simulation.ubl').read_bytes()
        sensor_example = (root / 'linux/microduck/sensor-simulation.ubp').read_bytes() + b'\n' + library + b'\n' + sensor_library
        robot_library = (root / 'linux/microduck/Robot_Simulation.ubl').read_bytes()
        telemetry_library = (root / 'linux/microduck/Robot_Telemetry.ubl').read_bytes()
        robot_example = (root / 'linux/microduck/robot-simulation.ubp').read_bytes() + b'\n' + library + b'\n' + sensor_library + b'\n' + robot_library + b'\n' + telemetry_library
        media_library = (root / 'linux/microduck/Media_Simulation.ubl').read_bytes()
        media_example = (root / 'linux/microduck/media-simulation.ubp').read_bytes() + b'\n' + library + b'\n' + media_library
        imu_library = (root / 'linux/microduck/Pad_IMU_Simulation.ubl').read_bytes()
        imu_example = (root / 'linux/microduck/pad-imu-simulation.ubp').read_bytes() + b'\n' + library + b'\n' + imu_library
        head_library = (root / 'linux/microduck/Head_IMU_Simulation.ubl').read_bytes()
        head_example = (root / 'linux/microduck/head-imu-simulation.ubp').read_bytes() + b'\n' + library + b'\n' + head_library
        head_service_library = (root / 'linux/microduck/Head_IMU.ubl').read_bytes()
        head_service_example = (root / 'linux/microduck/head-imu.ubp').read_bytes() + b'\n' + library + b'\n' + head_service_library
        depth_library = (root / 'linux/microduck/Depth.ubl').read_bytes()
        depth_example = (root / 'linux/microduck/depth.ubp').read_bytes() + b'\n' + library + b'\n' + depth_library
        gamepad_library = (root / 'linux/microduck/Gamepad.ubl').read_bytes()
        gamepad_example = (root / 'linux/microduck/gamepad.ubp').read_bytes() + b'\n' + library + b'\n' + gamepad_library
    packed = bytearray()
    entries = []
    counts = {'api': 0, 'compiler': 0, 'library': 0, 'arithmetic': 0, 'output': 0}
    for item in metadata['files']:
        name = item['filename']
        payload = data[int(item['start']):int(item['end'])]
        if name == '/runtime/lib/MicroBlocksCompiler.gp':
            payload = replace_once(payload, b"atPut primsets 'unoq' (at primsets 'io')", b"atPut primsets 'linux' (at primsets 'io')")
            if microduck:
                payload = replace_once(payload, b"atPut primsets 'linux' (at primsets 'io')",
                                       b"atPut primsets 'linux' (at primsets 'io')\n\tatPut primsets 'microduck' 22")
            counts['compiler'] += 1
        if name == '/runtime/lib/MicroBlocksAPI.gp':
            for before, after in [
                (b'// UNO Q: local, pinned files imported through the original editor/compiler.', b'// Linux: core-only library and local examples through the original editor/compiler.'),
                (b"'unoq.loadLibrary'", b"'linux.loadLibrary'"),
                (b"'unoq.openExample'", b"'linux.openExample'"),
                (b'Libraries/UNO_Q_Hardware.ubl', b'Libraries/Linux_Core.ubl'),
                (b"'UNO Q Hardware'", b"'Linux Core'"),
                (b"'Examples/UNO Q/'", b"'Examples/Linux/'"),
                (b"'arithmetic' 'output' 'rgb' 'matrix' 'combined' 'matrix-drawing'", b"'arithmetic' 'output'"),
            ]:
                payload = replace_once(payload, before, after)
            if b"endPoint == 'portal.serialize'" in payload or b"endPoint == 'portal.load'" in payload:
                raise ValueError('Project API was already injected')
            if microduck:
                payload = replace_once(payload, b"if (notNil data) { importLibraryFromString scripter data 'Linux Core' '' }",
                    b"if (notNil data) { importLibraryFromString scripter data 'Linux Core' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Linux.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Motion_Simulation.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Motion Simulation' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Sensor_Simulation.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Sensor Simulation' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Robot_Simulation.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Robot Simulation' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Robot_Telemetry.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Robot Telemetry Simulation' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Media_Simulation.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Media Simulation' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Pad_IMU_Simulation.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Pad IMU Simulation' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Head_IMU_Simulation.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Head IMU Simulation' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Head_IMU.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Head IMU' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Depth.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Depth' '' }\n"
                    b"\t\tdata = (readEmbeddedFile 'Libraries/MicroDuck_Gamepad.ubl')\n"
                    b"\t\tif (notNil data) { importLibraryFromString scripter data 'MicroDuck Gamepad' '' }")
                payload = replace_once(payload, b"'arithmetic' 'output'", b"'arithmetic' 'output' 'microduck-health' 'microduck-motion-simulation' 'microduck-sensor-simulation' 'microduck-robot-simulation' 'microduck-media-simulation' 'microduck-pad-imu-simulation' 'microduck-head-imu-simulation' 'microduck-head-imu' 'microduck-depth' 'microduck-gamepad'")
            payload = replace_once(payload, b"} (endPoint == 'project.save') {", PROJECT_API + b"} (endPoint == 'project.save') {")
            counts['api'] += 1
        if name == '/Libraries/UNO_Q_Hardware.ubl':
            name = '/Libraries/Linux_Core.ubl'; payload = LINUX_LIBRARY
            counts['library'] += 1
        if name.startswith('/Examples/UNO Q/'):
            basename = name.rsplit('/', 1)[-1]
            if basename not in ('arithmetic.ubp', 'output.ubp'):
                continue
            name = '/Examples/Linux/' + basename
            if basename == 'arithmetic.ubp':
                if b'script 102 48 (5 + 7)' not in payload or b'[unoq:' in payload:
                    raise ValueError('Unexpected pinned arithmetic example')
                counts['arithmetic'] += 1
            else:
                payload = replace_once(payload, b'repeat 500 {', b'repeat 50 {')
                payload = replace_once(payload,
                    b'Bounded physical IDE transport proof. No GPIO or FPGA programming.',
                    b'Bounded 50-value output example. Linux core runtime only; no GPIO.')
                if b'[unoq:' in payload:
                    raise ValueError('Hardware primitive found in Linux output example')
                counts['output'] += 1
        start = len(packed); packed.extend(payload)
        entries.append({'filename': name, 'start': start, 'end': len(packed)})
    if any(value != 1 for value in counts.values()):
        raise ValueError('Pinned Linux editor patch count differs: ' + repr(counts))
    if microduck:
        for name, payload in (('/Libraries/MicroDuck_Linux.ubl', library), ('/Examples/Linux/microduck-health.ubp', example),
                              ('/Libraries/MicroDuck_Motion_Simulation.ubl', motion_library),
                              ('/Examples/Linux/microduck-motion-simulation.ubp', motion_example),
                              ('/Libraries/MicroDuck_Sensor_Simulation.ubl', sensor_library),
                              ('/Examples/Linux/microduck-sensor-simulation.ubp', sensor_example),
                              ('/Libraries/MicroDuck_Robot_Simulation.ubl', robot_library),
                              ('/Libraries/MicroDuck_Robot_Telemetry.ubl', telemetry_library),
                              ('/Examples/Linux/microduck-robot-simulation.ubp', robot_example),
                              ('/Libraries/MicroDuck_Media_Simulation.ubl', media_library),
                              ('/Examples/Linux/microduck-media-simulation.ubp', media_example),
                              ('/Libraries/MicroDuck_Pad_IMU_Simulation.ubl', imu_library),
                              ('/Examples/Linux/microduck-pad-imu-simulation.ubp', imu_example),
                              ('/Libraries/MicroDuck_Head_IMU_Simulation.ubl', head_library),
                              ('/Examples/Linux/microduck-head-imu-simulation.ubp', head_example),
                              ('/Libraries/MicroDuck_Head_IMU.ubl', head_service_library),
                              ('/Examples/Linux/microduck-head-imu.ubp', head_service_example),
                              ('/Libraries/MicroDuck_Depth.ubl', depth_library),
                              ('/Examples/Linux/microduck-depth.ubp', depth_example),
                              ('/Libraries/MicroDuck_Gamepad.ubl', gamepad_library),
                              ('/Examples/Linux/microduck-gamepad.ubp', gamepad_example)):
            if name in {item['filename'] for item in entries}:
                raise ValueError('MicroDuck virtual file already exists: ' + name)
            start = len(packed); packed.extend(payload)
            entries.append({'filename': name, 'start': start, 'end': len(packed)})
    replacement = json.dumps({'files': entries, 'remote_package_size': len(packed)}, separators=(',', ':'))
    source = source[:match.start(1)] + replacement + source[match.end(1):]
    source = replace_once(source, '"/Examples","UNO Q"', '"/Examples","Linux"')
    return source.encode('utf-8'), bytes(packed)
