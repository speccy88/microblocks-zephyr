# SPDX-License-Identifier: MPL-2.0
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pages_linux_preview', ROOT / 'tools/package_pages_linux_preview.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PagesLinuxPreview(unittest.TestCase):
    def fixture(self, root):
        stable, linux = root / 'stable', root / 'linux'
        for folder, boards in ((stable, module.STABLE), (linux, module.STABLE | module.LINUX)):
            folder.mkdir()
            (folder / 'build-manifest.json').write_text(json.dumps({'boards': {
                board: {'hardware_connection_enabled': board not in ('microduck', 'xrp-rp2350')}
                for board in boards}}))
            for board in boards:
                target = folder / 'editor' / board
                target.mkdir(parents=True)
                (target / 'microblocks.html').write_text(folder.name + ':' + board)
            for name in ('portal.css', 'portal-core.js', 'LICENSE', 'LICENSES.md', 'UPSTREAM.md'):
                (folder / name).write_text(folder.name + ':' + name)
            (folder / 'licenses').mkdir()
            (folder / 'licenses/notice').write_text(folder.name)
        (stable / 'index.html').write_text('<select><option value="fruit-jam">Fruit Jam</option></select><script src="portal.js?v=old"></script>')
        (stable / 'portal.js').write_text("const path='editor/'+selected+'/microblocks.html';status.textContent=selected==='esp32p4'?'P4':'old';")
        return stable, linux

    def test_preserves_stable_assets_and_adds_only_preview_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stable, linux = self.fixture(root)
            before = module.files(stable), module.files(linux)
            output = root / 'output'
            report = module.build(stable, linux, output, 'a' * 40, 'b' * 40)
            self.assertEqual(before, (module.files(stable), module.files(linux)))
            for board in module.STABLE:
                self.assertEqual((output / 'editor' / board / 'microblocks.html').read_bytes(),
                                 (stable / 'editor' / board / 'microblocks.html').read_bytes())
            self.assertEqual({p.name for p in (output / 'preview/editor').iterdir()}, module.LINUX)
            self.assertIn('MicroDuck Rockchip RK3566 (experimental placeholder)', (output / 'index.html').read_text())
            self.assertIn("?'preview/':'')", (output / 'portal.js').read_text())
            self.assertFalse(report['public_deployment_performed'])

    def test_rejects_changed_stable_route_before_writing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stable, linux = self.fixture(root)
            (stable / 'portal.js').write_text('new stable routing')
            with self.assertRaisesRegex(ValueError, 'routing changed'):
                module.build(stable, linux, root / 'output', 'a' * 40, 'b' * 40)
            self.assertFalse((root / 'output').exists())

    def test_rejects_enabled_placeholder_or_overlapping_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stable, linux = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'separate trees'):
                module.build(stable, linux, stable / 'output', 'a' * 40, 'b' * 40)
            manifest = json.loads((linux / 'build-manifest.json').read_text())
            manifest['boards']['microduck']['hardware_connection_enabled'] = True
            (linux / 'build-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'remain disconnected'):
                module.build(stable, linux, root / 'output', 'a' * 40, 'b' * 40)


if __name__ == '__main__':
    unittest.main()
