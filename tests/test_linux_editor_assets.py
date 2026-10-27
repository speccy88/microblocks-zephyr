#!/usr/bin/env python3
"""Pinned GP source/package checks; no mock editor and no board access."""
# SPDX-License-Identifier: MPL-2.0
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
from linux_editor_assets import LINUX_LIBRARY, linux_package, unpack_package
from package_linux_editor import build, local_html, verified_assets


def fixture():
    files = {
        '/runtime/lib/MicroBlocksCompiler.gp': b"atPut primsets 'unoq' (at primsets 'io')\n",
        '/runtime/lib/MicroBlocksAPI.gp': b"""// UNO Q: local, pinned files imported through the original editor/compiler.
} (endPoint == 'unoq.loadLibrary') {
 data = (readEmbeddedFile 'Libraries/UNO_Q_Hardware.ubl')
 importLibraryFromString scripter data 'UNO Q Hardware' ''
} (endPoint == 'unoq.openExample') {
 if (isOneOf name 'arithmetic' 'output' 'rgb' 'matrix' 'combined' 'matrix-drawing') {
  data = (readEmbeddedFile (join 'Examples/UNO Q/' name '.ubp'))
 }
} (endPoint == 'project.save') {
 saveProjectToFile editor
}
""",
        '/Libraries/UNO_Q_Hardware.ubl': b"module 'UNO Q Hardware' Output\nspec ' ' '[unoq:setRGB]' 'RGB _' 'num' 1\n",
        '/Examples/UNO Q/arithmetic.ubp': b'module main\nscript 102 48 (5 + 7)\n',
        '/Examples/UNO Q/output.ubp': b"module main\ndescription 'Bounded physical IDE transport proof. No GPIO or FPGA programming.'\nrepeat 500 {\nsayIt 1\n}\n",
        '/Examples/UNO Q/rgb.ubp': b"module main\n'[unoq:setRGB]' 1 2 3\n",
        '/Examples/UNO Q/matrix.ubp': b"module main\n'[unoq:matrixShow]'\n",
        '/runtime/lib/Untouched.gp': b'// untouched engine source\n',
    }
    return encode(files)


def encode(files):
    packed = bytearray(); entries = []
    for name, payload in files.items():
        start = len(packed); packed.extend(payload)
        entries.append({'filename': name, 'start': start, 'end': len(packed)})
    metadata = json.dumps({'files': entries, 'remote_package_size': len(packed)}, separators=(',', ':'))
    metadata = re.sub(r'"(files|filename|start|end|remote_package_size)":', r'\1:', metadata)
    return ('beforeEngine();createPath("/Examples","UNO Q");loadPackage(' + metadata + ');afterEngine();').encode(), bytes(packed)


class LinuxPackage(unittest.TestCase):
    def test_core_alias_empty_library_examples_and_project_api(self):
        js, data = linux_package(*fixture()); files = unpack_package(js, data)
        self.assertIn(b"atPut primsets 'linux' (at primsets 'io')", files['/runtime/lib/MicroBlocksCompiler.gp'])
        api = files['/runtime/lib/MicroBlocksAPI.gp']
        for endpoint in [b'linux.loadLibrary', b'linux.openExample', b'portal.serialize', b'portal.load']:
            self.assertEqual(api.count(endpoint), 1)
        self.assertIn(b'openProject editor (at params 1) (at params 2)', api)
        self.assertIn(b'respondAPIRequest this id (codeString (project scripter))', api)
        self.assertEqual(files['/Libraries/Linux_Core.ubl'], LINUX_LIBRARY)
        self.assertNotRegex(LINUX_LIBRARY, rb'(?m)^(spec|to|script)\b')
        self.assertEqual(sorted(name for name in files if name.startswith('/Examples/')),
                         ['/Examples/Linux/arithmetic.ubp', '/Examples/Linux/output.ubp'])
        self.assertIn(b'repeat 50 {', files['/Examples/Linux/output.ubp'])
        self.assertNotIn(b'[unoq:', data)
        self.assertNotIn(b"'unoq.", data)
        self.assertNotIn(b'/Examples/UNO Q/', js)
        self.assertEqual(files['/runtime/lib/Untouched.gp'], b'// untouched engine source\n')
        self.assertTrue(js.startswith(b'beforeEngine();'))
        self.assertTrue(js.endswith(b'afterEngine();'))

    def test_does_not_patch_an_already_patched_or_drifted_source(self):
        js, data = fixture()
        with self.assertRaises(ValueError):
            linux_package(*linux_package(js, data))
        for before, after in [(b"primsets 'unoq'", b"primsets 'other'"),
                              (b"endPoint == 'project.save'", b"endPoint == 'renamed.save'"),
                              (b'repeat 500 {', b'repeat 501 {')]:
            with self.subTest(anchor=before), self.assertRaises(ValueError):
                linux_package(js, data.replace(before, after))

    def test_invalid_ranges_duplicates_and_missing_sources_fail(self):
        js, data = fixture()
        for changed in [data + b'extra', data[:-1]]:
            with self.assertRaises(ValueError):
                linux_package(js, changed)
        with self.assertRaises(ValueError):
            linux_package(js.replace(b'start:0', b'start:1', 1), data)
        files = unpack_package(js, data)
        files.pop('/runtime/lib/MicroBlocksCompiler.gp')
        with self.assertRaises(ValueError):
            linux_package(*encode(files))


class LocalBootstrap(unittest.TestCase):
    def html(self, query='v=26eb855451371f4c'):
        return ('<html><head><meta charset="utf-8">'
                '<script>Module.locateFile=function(name,prefix){return prefix+name+"?v=26eb855451371f4c";};</script>'
                '<script src="gp_wasm.js?' + query + '"></script></head><body>'
                '<script src="unoq-network.js"></script></body></html>').encode()
    def assets(self):
        return {name: b'' for name in ('gp_wasm.js', 'unoq-network.js', 'portal-core.js', 'portal.css')}

    def test_exact_local_assets_and_loopback_only_policy(self):
        for profile in ['raspberry-pi5', 'microduck']:
            html = local_html(self.html(), self.assets(), profile, 8876).decode()
            self.assertIn('return prefix+name;};', html)
            self.assertNotIn('?v=', html)
            self.assertNotIn('../../', html)
            self.assertIn('"runtime":"linux"', html)
            self.assertIn('"local_bridge":true', html)
            self.assertIn('"board":"' + profile + '"', html)
            self.assertIn("connect-src 'self' ws://127.0.0.1:8876 ws://localhost:8876;", html)
            self.assertNotIn(' wss:', html)
            self.assertNotIn('default_endpoint', html)

    def test_arbitrary_queries_and_remote_boot_resources_are_not_rewritten(self):
        with self.assertRaises(ValueError):
            local_html(self.html('token=something'), self.assets(), 'raspberry-pi5', 8876)
        with self.assertRaises(ValueError):
            local_html(self.html().replace(b'gp_wasm.js?v=', b'https://example.invalid/gp_wasm.js?v='),
                       self.assets(), 'raspberry-pi5', 8876)
        with self.assertRaises(ValueError):
            local_html(self.html(), self.assets(), 'esp32p4', 8876)
        with self.assertRaises(ValueError):
            local_html(self.html(), self.assets(), 'raspberry-pi5', 80)

    def test_source_hash_and_ownership_are_checked_before_writes(self):
        parent = REPO / 'build-artifacts/linux-editor-tests'; parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            root = Path(folder); repo = root / 'repo'; source = root / 'source'; output = root / 'output'
            (repo / 'dependencies').mkdir(parents=True); source.mkdir(); output.mkdir()
            (output / 'keep').write_bytes(b'user output')
            payload = b'source'; (source / 'gp_wasm.js').write_bytes(payload)
            manifest = {'files': [{'path': 'gp_wasm.js', 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}]}
            (repo / 'dependencies/ide-assets.json').write_text(json.dumps(manifest))
            self.assertEqual(verified_assets(source, repo)[1]['gp_wasm.js'], payload)
            (source / 'gp_wasm.js').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                build(source, output, repo)
            self.assertEqual((output / 'keep').read_bytes(), b'user output')


@unittest.skipUnless((REPO / 'build-artifacts/ide-source/gp_wasm.js').is_file(), 'pinned IDE source not staged')
class RealPinnedEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = REPO / 'build-artifacts/linux-editor-tests'; parent.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=parent)
        cls.output = Path(cls.temporary.name) / 'editor'
        cls.source = REPO / 'build-artifacts/ide-source'
        cls.report = build(cls.source, cls.output, REPO)
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_real_engine_and_pinned_filesystem_are_packaged(self):
        self.assertEqual(self.report['real_editor'], 'MicroBlocks GP 2.5.8')
        self.assertEqual(self.report['source_commit'], '70690291ac44a5c3a50dce572ee0c29ba99dc57f')
        self.assertEqual((self.output / 'gp_wasm.wasm').read_bytes(), (self.source / 'gp_wasm.wasm').read_bytes())
        self.assertGreater((self.output / 'gp_wasm.wasm').stat().st_size, 100000)
        files = unpack_package((self.output / 'gp_wasm.js').read_bytes(), (self.output / 'gp_wasm.data').read_bytes())
        self.assertIn('/runtime/lib/MicroBlocksCompiler.gp', files)
        self.assertIn('/runtime/lib/MicroBlocksEditor.gp', files)
        self.assertEqual(files['/Libraries/Linux_Core.ubl'], LINUX_LIBRARY)
        self.assertNotIn('/Libraries/UNO_Q_Hardware.ubl', files)
        self.assertIn(b"endPoint == 'portal.serialize'", files['/runtime/lib/MicroBlocksAPI.gp'])
        self.assertIn(b"endPoint == 'portal.load'", files['/runtime/lib/MicroBlocksAPI.gp'])

    def test_local_bootstrap_adapter_locale_and_notices(self):
        html = (self.output / 'microblocks.html').read_text()
        self.assertEqual((self.output / 'index.html').read_bytes(), (self.output / 'microblocks.html').read_bytes())
        self.assertNotIn('?v=', html); self.assertNotIn('../../', html)
        self.assertIn('board-ide-ready', html)
        self.assertIn('Module.locateFile=function(name,prefix){return prefix+name;};', html)
        self.assertIn(b'board-english', (self.output / 'gp_wasm.js').read_bytes())
        self.assertIn(b'GetText.ready = GetText.readLocale', (self.output / 'gettext.js').read_bytes())
        self.assertEqual((self.output / 'unoq-network.js').read_bytes(), (REPO / 'web/portal/portal-adapter.js').read_bytes())
        self.assertTrue((self.output / 'LICENSES.md').is_file())
        self.assertTrue((self.output / 'UPSTREAM.md').is_file())

    def test_owned_output_can_rebuild_but_other_output_is_preserved(self):
        report = build(self.source, self.output, REPO, 'microduck')
        self.assertEqual(report['profile'], 'microduck')
        other = self.output.parent / 'user-files'; other.mkdir(); (other / 'keep').write_bytes(b'keep')
        with self.assertRaises(ValueError):
            build(self.source, other, REPO)
        self.assertEqual((other / 'keep').read_bytes(), b'keep')

    def test_motion_simulation_library_is_separate_and_example_is_status_only(self):
        output = self.output.parent / 'motion-editor'
        build(self.source, output, REPO, 'microduck')
        files = unpack_package((output / 'gp_wasm.js').read_bytes(), (output / 'gp_wasm.data').read_bytes())
        library = (REPO / 'linux/microduck/Motion_Simulation.ubl').read_bytes()
        self.assertEqual(files['/Libraries/MicroDuck_Motion_Simulation.ubl'], library)
        self.assertIn(b"MicroDuck Motion Simulation", files['/runtime/lib/MicroBlocksAPI.gp'])
        self.assertIn(b"microduck-motion-simulation", files['/runtime/lib/MicroBlocksAPI.gp'])
        example = files['/Examples/Linux/microduck-motion-simulation.ubp']
        self.assertTrue(example.startswith((REPO / 'linux/microduck/motion-simulation.ubp').read_bytes()))
        self.assertIn(b'(microduckSimMotionStatus)', example)
        self.assertNotIn(b'(microduckSimMotionRun', example)
        core = unpack_package((self.output / 'gp_wasm.js').read_bytes(), (self.output / 'gp_wasm.data').read_bytes())
        self.assertNotIn('/Libraries/MicroDuck_Motion_Simulation.ubl', core)

    def test_sensor_simulation_library_and_read_only_example_are_embedded(self):
        output = self.output.parent / 'sensor-editor'
        build(self.source, output, REPO, 'microduck')
        files = unpack_package((output / 'gp_wasm.js').read_bytes(), (output / 'gp_wasm.data').read_bytes())
        self.assertEqual(files['/Libraries/MicroDuck_Sensor_Simulation.ubl'], (REPO / 'linux/microduck/Sensor_Simulation.ubl').read_bytes())
        self.assertIn(b'MicroDuck Sensor Simulation', files['/runtime/lib/MicroBlocksAPI.gp'])
        example = files['/Examples/Linux/microduck-sensor-simulation.ubp']
        self.assertTrue(example.startswith((REPO / 'linux/microduck/sensor-simulation.ubp').read_bytes()))
        self.assertIn(b'(microduckSimDepthRow depthCapture 1)', example)
        self.assertIn(b'(microduckSimPadButtonState padCapture 304)', example)
        self.assertNotIn(b'microduckSimMotionRun', example)
        core_output = self.output.parent / 'sensor-core-editor'
        build(self.source, core_output, REPO, 'raspberry-pi5')
        core = unpack_package((core_output / 'gp_wasm.js').read_bytes(), (core_output / 'gp_wasm.data').read_bytes())
        self.assertNotIn('/Libraries/MicroDuck_Sensor_Simulation.ubl', list(core))

    def test_robot_preview_telemetry_libraries_and_read_only_example_are_embedded(self):
        output = self.output.parent / 'robot-editor'
        build(self.source, output, REPO, 'microduck')
        files = unpack_package((output / 'gp_wasm.js').read_bytes(), (output / 'gp_wasm.data').read_bytes())
        for source, embedded in [('Robot_Simulation.ubl', 'MicroDuck_Robot_Simulation.ubl'), ('Robot_Telemetry.ubl', 'MicroDuck_Robot_Telemetry.ubl')]:
            self.assertEqual(files['/Libraries/' + embedded], (REPO / 'linux/microduck' / source).read_bytes())
        self.assertIn(b'MicroDuck Robot Telemetry Simulation', files['/runtime/lib/MicroBlocksAPI.gp'])
        example = files['/Examples/Linux/microduck-robot-simulation.ubp']
        self.assertTrue(example.startswith((REPO / 'linux/microduck/robot-simulation.ubp').read_bytes()))
        script = example.split(b'\nmodule ', 1)[0]
        self.assertIn(b'(microduckSimStateCapture 10)', script)
        self.assertNotIn(b'microduckSimRobotPreview', script)
        self.assertNotIn(b'microduckSimMovePreview', script)


if __name__ == '__main__':
    unittest.main()
