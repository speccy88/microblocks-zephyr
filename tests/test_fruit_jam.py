"""Fruit Jam source-backed pin safety and honest acceptance-state boundaries."""
import json
import re
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
        self.assertTrue(DATA['target_firmware_source_present'])
        self.assertTrue(all(not c['physical_tested'] for c in DATA['capabilities']))
        self.assertEqual(DATA['soc'],'RP2350B')

    def test_actual_arduino_pin_mapping_reserves_onboard_hardware(self):
        overlay=(ROOT/'boards/adafruit_fruit_jam/smallvm/app.overlay').read_text()
        value=re.search(r'digital-pin-gpios\s*=\s*(.*?);',overlay,re.S).group(1)
        pins=[int(pin)+(32 if port=='gpio0_hi' else 0)
              for port,pin in re.findall(r'<&(gpio0(?:_hi)?)\s+(\d+)\s+0>',value)]
        self.assertEqual(pins,DATA['digital_gpio'])
        self.assertEqual(set(pins),set(DATA['extension_gpio_allowlist']))
        self.assertNotIn(22,pins)
        self.assertNotIn(29,pins)
        io=(ROOT/'boards/adafruit_fruit_jam/smallvm/src/io.cpp').read_text()
        source_pins=[int(p) for p in re.search(r'physical_pins\[\]\s*=\s*\{([^}]+)',io).group(1).split(',')]
        self.assertEqual(source_pins,pins)

    def test_flash_storage_cannot_overlap_the_app(self):
        store=DATA['program_store']
        self.assertGreaterEqual(store['offset'],4*1024*1024)
        self.assertEqual(store['offset']+store['size'],DATA['flash_mib']*1024*1024)
        self.assertEqual(store['size'],store['slots']*store['slot_size'])
        self.assertLess(store['payload_offset']+store['ram_code_bytes'],store['slot_size'])
        dts=next((ROOT/'boards/adafruit_fruit_jam/zephyr/boards/adafruit/adafruit_fruit_jam').glob('*.dts')).read_text()
        self.assertIn('reg = <0xfc0000 0x40000>',dts)
        self.assertIn('reg = <0x0 DT_SIZE_M(4)>',dts)
        self.assertNotIn('zephyr,console',dts)

    def test_binary_transport_has_no_console_owner(self):
        app=ROOT/'boards/adafruit_fruit_jam/smallvm'
        conf=(app/'prj.conf').read_text()
        for name in ['CONSOLE','UART_CONSOLE','PRINTK','LOG','SHELL','BOOT_BANNER']:
            self.assertIn(f'CONFIG_{name}=n',conf)
        text=(app/'src/transport.c').read_text()
        self.assertNotIn('printk(',text)
        self.assertNotIn('Serial.begin',text)
        self.assertIn('smallvmResetTransport();',text)
        self.assertIn('if (!connected ||',text)

    def test_pwm_channels_do_not_alias_other_extension_pins(self):
        channels=DATA['pwm_channels']
        self.assertEqual(len(channels),len(set(channels)))
        self.assertEqual(channels,[p-24 if p>=32 else p%16 for p in DATA['digital_gpio']])

if __name__=='__main__':unittest.main()
