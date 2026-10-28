# SPDX-License-Identifier: MPL-2.0
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_js_editor import package


class JSP4Services(unittest.TestCase):
    def test_secure_network_transport_with_actual_connection(self):
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        if not node or not (source / '.git').exists():
            self.skipTest('Pinned source and Node required')
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / 'p4'
            package(source, assets, profile='esp32p4')
            result = subprocess.run([node, str(ROOT / 'tests/js-p4-network.test.cjs'), str(assets)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1])['passed'], 5)

    def test_actual_connection_and_typed_service_lifecycle(self):
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        if not node or not (source / '.git').exists():
            self.skipTest('Pinned source and Node required')
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / 'p4'
            package(source, assets, profile='esp32p4')
            record = json.loads((assets / 'p4-service-sources.json').read_text())
            for entry in record['sources']:
                raw = (assets / entry['packaged_path']).read_bytes()
                self.assertEqual(raw, (ROOT / entry['source_path']).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
            self.assertFalse((assets / 'device-files-fixture.js').exists())
            result = subprocess.run([node, str(ROOT / 'tests/js-p4-services.test.cjs'), str(assets)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report['passed'], 8)
            self.assertTrue(report['actual_pinned_connection'])
            self.assertTrue(report['typed_file_controller'])

    def test_actual_connection_routes_native_storage_and_pinned_sender(self):
        gcc = shutil.which('gcc')
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        upstream = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        if platform.system() != 'Linux' or not gcc or not node or not (upstream / '.git').exists():
            self.skipTest('Linux GCC, Node and verified upstream required')
        manifest = json.loads((ROOT / 'dependencies/smallvm-v417.json').read_text())
        entry = next(item for item in manifest['files'] if item['path'] == 'vm/runtime.c')
        raw = subprocess.check_output(['git', '-C', str(upstream), 'cat-file', 'blob', entry['git_blob']])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
        text = raw.decode('utf-8')
        def function(signature):
            start = text.index(signature + ' {')
            return text[start:text.index('\n}', start) + 2]
        sender = function('static void sendMessage(int msgType, int chunkIndex, int dataSize, char *data)') + '\n' + function('void waitAndSendMessage(int msgType, int chunkIndex, int dataSize, char *data)') + '\n'
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'vm').mkdir()
            (folder / 'vm/interp.h').write_text('int hasOutputSpace(int n);\nvoid waitAndSendMessage(int,int,int,char *);\n')
            (folder / 'vm_sender.inc').write_text(sender)
            binary = folder / 'native-storage'
            sources = [ROOT / 'common/storage' / name for name in ('storage.c', 'dispatcher.c', 'wire.c', 'controller.c', 'storage_protocol.c')]
            command = [gcc, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I' + str(folder), '-I' + str(ROOT / 'common/storage'), *map(str, sources), str(ROOT / 'tests/storage_vm_fakes.c'), str(ROOT / 'tests/storage_application_host.c'), '-o', str(binary)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            assets = folder / 'p4'
            package(source, assets, profile='esp32p4')
            env = os.environ.copy()
            config = {'binary': str(binary), 'distribution': None}
            node_platform = subprocess.check_output([node, '-p', 'process.platform'], text=True).strip()
            if node_platform == 'win32':
                self.assertTrue(env.get('WSL_DISTRO_NAME'), 'Explicit WSL distribution required for Windows Node')
                config['distribution'] = env['WSL_DISTRO_NAME']
            result = subprocess.run([node, str(ROOT / 'tests/js-p4-services.test.cjs'), str(assets), '--native', json.dumps(config)],
                                    capture_output=True, text=True, timeout=45, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertTrue(report['native_storage_service'])
            self.assertTrue(report['conditional_writes'])
            self.assertTrue(report['exact_bytes'])
            print(json.dumps({'js_p4_native_storage': report,
                'pinned_runtime_sha256': entry['sha256'],
                'sender_sha256': hashlib.sha256(sender.encode()).hexdigest(),
                'sanitized_fixture_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    unittest.main()
