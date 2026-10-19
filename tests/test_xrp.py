"""Production pin ownership and baseline safety contracts; no hardware PASS."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'boards/sparkfun_xrp_rp2350'
DATA = json.loads((BOARD / 'hardware.json').read_text(encoding='utf-8'))
DTS = (BOARD / 'zephyr/boards/sparkfun/sparkfun_xrp/sparkfun_xrp_rp2350b_m33_0.dts').read_text()


class XRPProductionContracts(unittest.TestCase):
    def test_no_beta_or_wrong_soc_claim(self):
        self.assertFalse(DATA['beta'])
        self.assertEqual(DATA['soc'], 'RP2350B')
        self.assertFalse(DATA['physical_identity_verified'])
        self.assertFalse(DATA['portal_hardware_connection_enabled'])
        self.assertFalse(DATA['psram_mapped'])

    def test_motor_gpio_ports_match_canonical_production_pin_map(self):
        section = re.search(r'motor-input-gpios\s*=\s*(.*?);', DTS, re.S)[1]
        ports = re.findall(r'<&(gpio0_hi|gpio0)\s+(\d+)\s+GPIO_ACTIVE_HIGH>', section)
        actual = [int(pin) + (32 if port == 'gpio0_hi' else 0) for port, pin in ports]
        expected = [pin for motor in DATA['motors'] for pin in (motor['in1'], motor['in2'])]
        self.assertEqual(actual, expected)
        self.assertEqual(actual, [34, 35, 32, 33, 20, 21, 10, 11])
        self.assertIn('dual-input PWM', DATA['motor_driver'])

    def test_reserved_pins_are_not_generic_extension_pins(self):
        used = {pin for motor in DATA['motors'] for pin in
                (motor['in1'], motor['in2'], motor['encoder_a'], motor['encoder_b'])}
        used.update(DATA['servos_gpio_in_connector_order'])
        capabilities = {c['id']: c for c in DATA['capabilities']}
        for capability in DATA['capabilities']:
            if capability['id'] != 'external_gpio':
                used.update(v for v in capability.get('pins', {}).values() if isinstance(v, int))
        safe = set(capabilities['external_gpio']['pins']['unreserved'])
        self.assertFalse(safe & used)
        self.assertEqual(safe, set(range(12, 20)))
        self.assertEqual(DATA['servos_gpio_in_connector_order'], [6, 9, 7, 8])
        self.assertEqual(capabilities['qwiic1']['pins'], {'sda': 38, 'scl': 39})

    def test_partitions_do_not_overlap_and_baseline_has_no_actuator_or_storage_commands(self):
        regions = sorted((p['offset'], p['offset'] + p['size']) for p in DATA['partitions'].values())
        self.assertGreater(regions[0][1], 0)
        for a, b in zip(regions, regions[1:]):
            self.assertLessEqual(a[1], b[0])
        self.assertLessEqual(regions[-1][1], DATA['flash_mib'] * 1024 * 1024)
        main = (BOARD / 'bringup/src/main.c').read_text()
        for forbidden in ('pwm_set', 'flash_write', 'flash_erase', 'WIFI_CONNECT', 'sys_reboot'):
            self.assertNotIn(forbidden, main)
        self.assertIn('GPIO_OUTPUT_INACTIVE', main)
        self.assertIn('i2c_reg_read_byte(imu_bus, 0x6b, 0x0f', main)
        self.assertTrue(all(not c['physical_tested'] for c in DATA['capabilities']))
