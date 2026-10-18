"""Fruit Jam source-backed pin safety and honest acceptance-state boundaries."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'boards/adafruit_fruit_jam/hardware.json').read_text(encoding='utf-8'))

class FruitJamInventoryTests(unittest.TestCase):
    def test_safe_extension_pins_and_high_bank_adc(self):
        caps={c['id']:c for c in DATA['capabilities']}
        reserved=set()
        for feature in caps.values():
            if feature['id']=='expansion':continue
            for value in feature['pins'].values():
                reserved.update(value if isinstance(value,list) else [value])
        self.assertFalse(set(DATA['extension_gpio_allowlist']) & reserved)
        self.assertEqual(DATA['analog_gpio'],[40,41,42,43,44,45])
        self.assertNotIn(46,DATA['extension_gpio_allowlist'])
        self.assertNotIn(47,DATA['extension_gpio_allowlist'])
        self.assertEqual(caps['sdcard']['pins']['detect'],33)

    def test_debug_reset_and_acceptance_are_explicit(self):
        self.assertEqual(DATA['swd']['pins'],{'1':'SWCLK','2':'GND','3':'SWDIO'})
        self.assertIn('RUN',DATA['swd']['main_reset'])
        self.assertFalse(DATA['target_firmware_cross_built'])
        self.assertFalse(DATA['target_firmware_implemented'])
        self.assertTrue(all(not c['physical_tested'] for c in DATA['capabilities']))
        self.assertEqual(DATA['soc'],'RP2350B')

if __name__=='__main__':unittest.main()
