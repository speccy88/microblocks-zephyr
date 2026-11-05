"""Optional peripherals: actual C behavior and independent packaging contracts."""
# SPDX-License-Identifier: MIT
import os
import re
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
    def test_optional_primitive_names_match_native_abi(self):
        native=ROOT/'boards/propeller2/native'
        sources={'display':['propeller2/p2OutputPrims.c'],'serial':['propeller2/p2SerialPrims.c'],
                 'file':['propeller2/p2Files.c'],'sensors':['propeller2/p2SensorPrims.c'],
                 'data':['vm/dataPrims.c'],'misc':['vm/miscPrims.c'],'p2':['propeller2/p2IOPrims.c']}
        entries={name:set(re.findall(r'\{\s*"([^"]+)"\s*,','\n'.join((native/p).read_text(encoding='utf-8') for p in paths)))
                 for name,paths in sources.items()}
        libraries=list((ROOT/'boards/propeller2/integration/libraries').glob('*.ubl'))+list((ROOT/'libraries').rglob('*.ubl'))
        for path in libraries:
            for group,name in re.findall(r'\[([a-z0-9]+):([^\]]+)\]',path.read_text(encoding='utf-8')):
                self.assertIn(name,entries[group],str(path)+': '+group+':'+name)

    def test_optional_libraries_are_available_but_not_automatic(self):
        files = target_assets('propeller2')
        self.assertIn('Libraries/P2/P2 LEDs.ubl', files)
        self.assertIn('Examples/P2/leds.ubp', files)
        self.assertNotIn(b'module \'P2 LEDs\'', files['Libraries/Targets/Propeller 2 Project.ubl'])

    def test_led_production_buffer_and_validation(self):
        self.run_host('p2_led_host.c')

    def test_ssd1331_production_graphics_and_validation(self):
        self.run_host('p2_display_host.c')

    def test_uart_production_rings_and_validation(self):
        self.run_host('p2_uart_host.c')

    def test_files_production_namespace_and_io(self):
        self.run_host('p2_files_host.c')

    def test_dht22_production_decoder_and_timeouts(self):
        self.run_host('p2_dht_host.c')

    def test_keypad_production_scan_and_ghosts(self):
        self.run_host('p2_keypad_host.c')

    def test_shift_register_production_bit_order(self):
        self.run_host('p2_shift_host.c')

    def test_ping_production_echo_and_timeouts(self):
        self.run_host('p2_ping_host.c')

    def test_audio_production_pcm_queue_and_volume(self):
        self.run_host('p2_audio_host.c')

    def test_candidate_storage_never_formats_on_mount(self):
        source=(ROOT/'boards/propeller2/native/propeller2/p2PersistFile.c').read_text(encoding='utf-8')
        self.assertIn('_vfs_open_littlefs_flash(0, &cfg)',source)
        self.assertNotIn('_mkfs_',source)

    def run_host(self, name):
        with tempfile.TemporaryDirectory(prefix='p2-peripherals-') as temp:
            exe = Path(temp)/('led.exe' if os.name=='nt' else 'led')
            includes = str(ROOT/'tests/p2_peripheral_stubs')
            source = str(ROOT/'tests'/name)
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
            run = subprocess.run([str(exe)],cwd=temp,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn('PASS',run.stdout)
