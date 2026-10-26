"""Guard the non-deployable Flash experiment and existing physical RAM target."""
# SPDX-License-Identifier: MIT
import re
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'boards/waveshare_esp32p4_wifi6/zephyr'

class FlashLocalContract(unittest.TestCase):
    def test_no_production_link_partition_or_available_claim(self):
        cmake = (PORT / 'CMakeLists.txt').read_text()
        self.assertNotIn('flash_store.c', cmake)
        self.assertNotIn('zephyr_flash.c', cmake)
        for filename, expected in [('hosted.overlay', [(0x2000,0xfde000),(0xfe0000,0x1000000),(0x1fe0000,0x20000)]),
                                   ('whistle.overlay', [(0x2000,0xfde000),(0xfe0000,0x1020000)])]:
            text = (PORT / 'profiles' / filename).read_text()
            actual = [tuple(int(x,16) for x in pair) for pair in re.findall(r'reg\s*=\s*<(0x[0-9a-f]+)\s+(0x[0-9a-f]+)>',text)]
            self.assertEqual(actual,expected)
            self.assertNotIn('p4_user_files',text)
        self.assertIn('Flash and SD are unavailable',(ROOT/'integration/Storage.ubl').read_text())

    def test_no_automatic_format_and_no_untrusted_vfs_paths(self):
        text = (ROOT/'common/storage/flash/zephyr_flash.c').read_text()
        self.assertIn('flags|=FS_MOUNT_FLAG_NO_FORMAT',text)
        self.assertNotRegex(text,r'\b(?:fs_mkfs|flash_erase|flash_write|lfs_format)\s*\(')
        self.assertIn('static const char *const paths[]',text)
        self.assertIn('fs_sync(&file)',text)
        self.assertIn('fs_rename(tmp,paths[key])',text)
        self.assertIn('if(key>=9',text)

    def test_destructive_fixture_is_simulator_only(self):
        text = (ROOT/'tests/flash_native/CMakeLists.txt').read_text()
        self.assertIn('if(NOT CONFIG_BOARD_NATIVE_SIM)',text)
        self.assertIn('FATAL_ERROR',text)
        self.assertIn('CONFIG_ASAN=y',(ROOT/'tests/flash_native/prj.conf').read_text())

    def test_core_is_portable_bounded_and_separate(self):
        text=(ROOT/'common/storage/flash/flash_store.c').read_text()
        self.assertNotIn('zephyr/',text)
        self.assertNotRegex(text,r'\b(?:malloc|calloc|realloc|free|fopen|fs_open|flash_write)\s*\(')
        header=(ROOT/'common/storage/flash/flash_store.h').read_text()
        for symbol,value in [('MB_FLASH_FILES',8),('MB_FLASH_BYTES',8192),('MB_FLASH_PATH',64)]:
            self.assertIn(f'#define {symbol} {value}',header)
        self.assertIn('s->ready=false',text)
        self.assertIn('MB_FLASH_REV_MAX',text)

if __name__ == '__main__': unittest.main()
