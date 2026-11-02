from pathlib import Path
import sys
import asyncio
import json
import tempfile
from unittest.mock import AsyncMock, patch
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux/arm64'))
from lan_service import vm_arguments
import lan_service


class ServiceArgumentsTests(unittest.TestCase):
    def test_default_vm_paths_are_explicit(self):
        self.assertEqual(vm_arguments({}, '/binary', '/data', '/data/pty.json'),
            ['/binary', '--data-dir', '/data', '--pty-info', '/data/pty.json'])

    @unittest.skipUnless(sys.platform == 'linux', 'Canonical POSIX private socket paths')
    def test_existing_private_gateway_is_preserved(self):
        args = vm_arguments({'microduck_socket': '/private/extensions.sock'}, '/binary', '/data', '/data/pty.json')
        self.assertEqual(args[-2:], ['--microduck-socket', '/private/extensions.sock'])

    def test_invalid_gateway_paths_are_refused(self):
        for value in ('', 'relative.sock', '../escape', False):
            with self.assertRaises(RuntimeError):
                vm_arguments({'microduck_socket': value}, '/binary', '/data', '/data/pty.json')


class RecoveryOrderTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(sys.platform == 'linux', 'Managed Linux recovery filesystem')
    async def test_failed_candidate_restores_config_before_python_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'updates').mkdir()
            (root / 'data').mkdir()
            previous = {'schema': 1, 'binary': 'previous/smallvm', 'python_extensions': {'profile': 'previous.json'}}
            candidate = {'schema': 1, 'binary': 'candidate/smallvm', 'python_extensions': {'profile': 'candidate.json'}}
            (root / 'service.json').write_text(json.dumps(candidate))
            (root / 'updates/pending.json').write_text(json.dumps({
                'boot_attempted': True, 'previous_config': previous, 'program_existed': False,
                'version': 'failed-candidate', 'sha256': 'a' * 64}))
            seen = []
            class FakePython:
                def __init__(self, selected_root, config):
                    seen.append(config)
                async def __aenter__(self): return None
                async def __aexit__(self, *error): return None
            runtime = AsyncMock()
            with patch.object(lan_service, 'private_root', return_value=root), patch.object(lan_service, 'ManagedPython', FakePython), patch.object(lan_service, 'run_runtime', runtime):
                await lan_service.run(root)
            self.assertEqual(seen, [previous])
            runtime.assert_awaited_once_with(root, previous)
            self.assertEqual(json.loads((root / 'updates/state.json').read_text())['state'], 'rolled_back')


if __name__ == '__main__': unittest.main()
