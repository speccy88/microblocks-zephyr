"""RGB conversion, browser core and packaged fixture acceptance; no physical camera."""
import importlib.util,json,os,pathlib,shutil,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('camera_rgb',ROOT/'linux/microduck/camera_rgb.py');rgb=importlib.util.module_from_spec(spec);spec.loader.exec_module(rgb)

class RGBPreview(unittest.TestCase):
    def test_python_known_colors_clipping_and_component_validation(self):
        for raw,expected in [((16,128,128),0),((235,128,128),0xffffff),((81,90,240),0xff0000),((41,240,110),255),((0,10,20),0x7300)]:
            self.assertEqual(rgb.rgb24(*raw),expected)
        for invalid in (-1,256,1.5,True,None):
            with self.assertRaises(ValueError):rgb.rgb24(invalid,128,128)
    def test_browser_conversion_bounds_rotations_and_lifecycle(self):
        node=os.environ.get('NODE_BINARY') or shutil.which('node')
        if not node:self.skipTest('Node required')
        # Bound Node's package lookup locally; Windows Node cannot traverse
        # above a WSL share. node:test runs without --test's extra worker.
        with tempfile.TemporaryDirectory(prefix='camera-rgb-node-') as folder:
            work=pathlib.Path(folder)
            (work/'package.json').write_text('{"type":"commonjs"}')
            for name in ('tests/test_microduck_camera_rgb.cjs','web/microduck/camera-rgb.js'):
                target=work/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/name).read_bytes())
                self.assertEqual(target.read_bytes(),(ROOT/name).read_bytes())
            result=subprocess.run([node,'--test-reporter=tap',str(work/'tests/test_microduck_camera_rgb.cjs')],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('# pass 6',result.stdout)
    def test_fixture_page_has_no_connection_or_automatic_capture(self):
        page=(ROOT/'web/microduck/camera-rgb.html').read_text();lab=(ROOT/'web/microduck/camera-rgb-lab.js').read_text()
        self.assertIn("connect-src 'none'",page);self.assertIn('FICTIONAL UYVY DATA',page)
        for denied in ('fetch(', 'WebSocket(', 'getUserMedia(', 'setInterval(', 'toDataURL(', 'createObjectURL('):self.assertNotIn(denied,lab)
        self.assertIn("'visibilitychange'",lab);self.assertIn("'pagehide'",lab)
        self.assertEqual((ROOT/'web/microduck/camera-rgb-LICENSE.txt').read_bytes(),(ROOT/'licenses/Apache-2.0.txt').read_bytes())
        self.assertIn("'camera-rgb.html'",(ROOT/'tools/package_pages.py').read_text())
