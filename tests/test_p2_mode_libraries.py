"""Mode ownership, compatibility and automatic setup contracts; no board I/O."""
import re
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from p2_library_groups import GROUPS, split_library, library_dependencies

class ModeLibraries(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / 'boards/propeller2/integration/P2_Hardware.ubl').read_bytes()
        self.files, self.owners = split_library(self.raw)
        self.deps = library_dependencies(self.files)

    def test_unique_unchanged_public_api(self):
        canonical = self.raw.decode().replace('\r\n', '\n')
        combined = '\n'.join(data.decode().replace('\r\n', '\n') for data in self.files.values())
        self.assertEqual(sorted(re.findall(r'^spec .+$', canonical, re.M)),
                         sorted(re.findall(r'^spec .+$', combined, re.M)))
        bodies = lambda text: sorted(re.findall(r'^to \w+[^\n]*\{.*?\}', text, re.M | re.S))
        self.assertEqual(bodies(canonical), bodies(combined))
        functions = re.findall(r'^to (\w+)', combined, re.M)
        self.assertEqual(len(functions), 82)
        self.assertEqual(len(functions), len(set(functions)))

    def test_small_palettes_and_dependency_graph(self):
        for name, _ in GROUPS:
            data = self.files[f'Libraries/P2/{name}.ubl'].decode()
            if name != 'P2 Advanced':
                self.assertLessEqual(len(re.findall('^spec ', data.split('\nadvanced\n')[0], re.M)), 10, name)
            def visit(current, chain):
                self.assertNotIn(current, chain)
                for dep in self.deps[current]:
                    self.assertIn(dep, self.deps)
                    visit(dep, chain + [current])
            visit(name, [])
            for body in re.findall(r'^to \w+[^\n]*\{.*?\}', data, re.M | re.S):
                for called in re.findall(r'\b(p2\w+)\b', body):
                    if called in self.owners and self.owners[called] != name:
                        self.assertIn(self.owners[called], self.deps[name], (name, called))
            closure = set()
            def collect(current):
                if current in closure:
                    return
                closure.add(current)
                for dep in self.deps[current]:
                    collect(dep)
            collect(name)
            available = '\n'.join(self.files[f'Libraries/P2/{dep}.ubl'].decode() for dep in closure)
            choices = set(re.findall(r'^choices (\w+)', available, re.M))
            self.assertTrue(set(re.findall(r'menu\.(\w+)', data)) <= choices, name)
        self.assertIn('P2 Serial Data', self.deps['P2 UART'])
        self.assertIn('P2 Capture Control', self.deps['P2 SINC Stream'])

    def test_simple_io_sets_mode_before_read(self):
        source = self.files['Libraries/P2/P2 Simple IO.ubl'].decode()
        self.assertIn("'[p2:p2PadNamed]' pin 'logic' true high", source)
        self.assertIn("'[p2:p2SmartPin]' pin bias 0 0", source)
        self.assertIn("if (not (p2DigitalInput pin bias)) { return false }", source)
        self.assertIn("return ('[p2:p2PinSample]' pin)", source)
        self.assertIn("(bias == 'input') (bias == 'pull-up') (bias == 'pull-down')", source)
        native = (ROOT / 'boards/propeller2/native/propeller2/p2IOPrims.c').read_text()
        self.assertIn('static void p2Pad(int pin, uint32_t pad, int drive, int high) {\n\treleasePin(pin);', native)
        for primitive in ['primP2PadNamed', 'primP2SmartPin']:
            body = native.split('static OBJ ' + primitive + '(')[1].split('\n}')[0]
            self.assertIn('p2PinArg(argc, args)', body)
        self.assertIn('if (!strcmp(name, "input")) { releasePin(pin); return trueObj; }', native)
        # Argument rejection happens before any output/mode change.
        pad = native.split('static OBJ primP2PadNamed(')[1].split('\n}')[0]
        self.assertLess(pad.index('objType(args[3]) != BooleanType'), pad.index('p2Pad(pin,'))
        self.assertLess(pad.index('return falseObj;'), pad.index('p2Pad(pin,'))
        pin_arg = native.split('static int p2PinArg(')[1].split('\n}')[0]
        self.assertIn('!isInt(args[0])', pin_arg)
        self.assertIn('validPin(pin) ? pin : -1', pin_arg)
        start = native.split('static void p2Start(')[1].split('\n}')[0]
        self.assertLess(start.index('releasePin(pin)'), start.index('_pinstart(pin, mode, x, y)'))
        self.assertIn('if (operation == P_PULSE || operation == P_TRANSITION) _wypin(pin, y);', start)


if __name__ == '__main__':
    unittest.main()
