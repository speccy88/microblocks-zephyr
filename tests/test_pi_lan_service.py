from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux/arm64'))
from lan_service import vm_arguments


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


if __name__ == '__main__': unittest.main()
