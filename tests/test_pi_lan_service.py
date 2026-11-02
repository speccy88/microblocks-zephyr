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
    def test_proxy_configuration_preserves_both_explicit_origins(self):
        config = {'origin': 'http://192.168.2.50', 'backend_port': 8877,
            'additional_origins': ['http://100.100.10.20']}
        policy = lan_service.policy_for_config(config)
        self.assertEqual(policy.bind, '127.0.0.1')
        self.assertEqual(policy.origins, [config['origin'], *config['additional_origins']])
        self.assertEqual(lan_service.policy_for_config({k: v for k, v in config.items() if k != 'additional_origins'}).origins,
            [config['origin']])

    def test_direct_listener_cannot_claim_additional_proxy_origins(self):
        config = {'direct_bind': '127.0.0.1', 'backend_port': 8877,
            'clients': '127.0.0.1/32', 'origin': 'http://127.0.0.1:8877'}
        self.assertEqual(lan_service.policy_for_config(config).origins, [config['origin']])
        with self.assertRaises(RuntimeError):
            lan_service.policy_for_config({**config, 'additional_origins': ['http://100.100.10.20']})
        with self.assertRaises(RuntimeError):
            lan_service.policy_for_config({**config, 'origin': 'http://100.100.10.20'})

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
            previous = {'schema': 1, 'binary': 'previous/smallvm', 'python_extensions': {'profile': 'previous.json'},
                'origin': 'http://192.168.2.50', 'additional_origins': ['http://100.100.10.20']}
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
