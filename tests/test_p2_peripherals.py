"""Optional peripherals: actual C behavior and independent packaging contracts."""
# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from js_editor_shared_assets import target_assets


class P2Peripherals(unittest.TestCase):
    def test_optional_libraries_are_available_but_not_automatic(self):
        files = target_assets('propeller2')
        self.assertIn('Libraries/P2/P2 LEDs.ubl', files)
        self.assertIn('Examples/P2/leds.ubp', files)
        self.assertNotIn(b'module \'P2 LEDs\'', files['Libraries/Targets/Propeller 2 Project.ubl'])

    def test_led_production_buffer_and_validation(self):
        with tempfile.TemporaryDirectory(prefix='p2-peripherals-') as temp:
            exe = Path(temp)/('led.exe' if os.name=='nt' else 'led')
            includes = str(ROOT/'tests/p2_peripheral_stubs')
            source = str(ROOT/'tests/p2_led_host.c')
            cc = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
            if cc:
                command = [cc,'-std=c11','-Wall','-Wextra','-Werror','-I'+includes,source,'-o',str(exe)]
            elif os.name=='nt':
                vc = Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat')
                if not vc.exists(): self.skipTest('No host C compiler; native FlexC build is separate')
                batch = Path(temp)/'build.cmd'
                batch.write_text(f'@call "{vc}" >nul\n@cl /nologo /std:c11 /W4 /I"{includes}" "{source}" /Fe:"{exe}" /Fo:"{temp}\\led.obj"\n', encoding='utf-8')
                command = ['cmd.exe','/d','/c',str(batch)]
            else: self.skipTest('No host C compiler')
            result = subprocess.run(command,cwd=temp,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            run = subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn('PASS',run.stdout)
