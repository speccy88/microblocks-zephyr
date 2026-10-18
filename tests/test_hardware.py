"""Offline checks. These DO NOT emulate Zephyr, the ESP32 or SmallVM."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "boards" / "waveshare_esp32s3_rlcd_4_2" / "hardware.json").read_text(encoding="utf-8"))
CAPS = {x["id"]: x for x in DATA["capabilities"]}


class HardwareManifestTests(unittest.TestCase):
    def test_known_zephyr_target(self):
        self.assertEqual(DATA["zephyr_target"], "esp32s3_rlcd_4_2/esp32s3/procpu")
        self.assertEqual(DATA["flash_mib"], 16)
        self.assertEqual(DATA["psram_mib"], 8)

    def test_unique_features_and_no_invented_touch(self):
        self.assertEqual(len(CAPS), len(DATA["capabilities"]))
        self.assertFalse(DATA["declared_touchscreen"])
        self.assertNotIn("touchscreen", CAPS)

    def test_shtc3_and_rtc_addresses(self):
        self.assertEqual(CAPS["temperature_humidity"]["address"], "0x70")
        self.assertEqual(CAPS["rtc"]["address"], "0x51")
        self.assertEqual(CAPS["speaker_dac"]["address"], "0x18")
        self.assertEqual(CAPS["mic_adc"]["address"], "0x40")

    def test_pin_buses_match_zephyr_dt(self):
        pins = CAPS["display"]["pins"]
        self.assertEqual((pins["clk"], pins["mosi"], pins["cs"], pins["dc"], pins["reset"]),
                         (11, 12, 40, 5, 41))
        self.assertEqual(CAPS["temperature_humidity"]["pins"]["sda"], 13)
        self.assertEqual(CAPS["rtc"]["pins"]["scl"], 14)
        self.assertEqual(CAPS["buttons"]["pins"], {"boot": 0, "key": 18})
        self.assertEqual(CAPS["sdcard"]["pins"], {"cmd": 21, "clk": 38, "d0": 39})

    def test_do_not_offer_shared_pins_as_unreserved(self):
        safe_candidates = set(CAPS["external_gpio"]["pins"]["candidate_unreserved"])
        used = set()
        for feat in CAPS.values():
            if feat["id"] == "external_gpio" or feat.get("scope") == "extension":
                continue
            used.update(x for x in feat.get("pins", {}).values() if isinstance(x, int))
        self.assertFalse(safe_candidates & used)

    def test_extension_multiplexing_and_battery_channel(self):
        safe = {1, 2, 17}
        self.assertEqual(set(CAPS["external_gpio"]["pins"]["candidate_unreserved"]), safe)
        self.assertEqual(CAPS["battery_adc"]["pins"]["signal"], 4)
        self.assertEqual(CAPS["analog_inputs"]["pins"], {"a0": 1, "a1": 2})
        self.assertEqual(CAPS["external_spi"]["pins"], {"sclk": 1, "mosi": 2, "miso": 17})
        self.assertEqual(CAPS["pwm"]["pins"], {"output": 17})
        for feature in CAPS.values():
            if feature.get("scope") == "extension":
                self.assertTrue(set(feature["pins"].values()) <= safe)

    def test_not_claiming_unbuilt_hardware_implemented(self):
        for name in ("wifi", "ble", "mic_adc", "speaker_dac", "sdcard", "sleep_power"):
            self.assertNotEqual(CAPS[name]["bringup"], "diagnostic-implemented")

    def test_port_tree_is_multiboard_ready(self):
        self.assertTrue((ROOT / "boards" / "waveshare_esp32s3_rlcd_4_2" / "README.md").is_file())
        self.assertTrue((ROOT / "docs" / "ARCHITECTURE.md").is_file())
        self.assertTrue((ROOT / "AGENTS.md").is_file())

    def test_unintegrated_features_are_explicitly_marked(self):
        self.assertTrue(any(c["smallvm"] == "planned" for c in CAPS.values()))
        self.assertIn("SmallVM", (ROOT / "README.md").read_text())

    def test_compilation_guard_exists(self):
        src = (ROOT / "boards" / "waveshare_esp32s3_rlcd_4_2" / "bringup" / "src" / "rlcd_board.c").read_text()
        self.assertIn('DT_NODELABEL(shtc3)', src)
        self.assertIn('DT_CHOSEN(zephyr_display)', src)
        self.assertIn('display_write(', src)
        self.assertIn('sensor_sample_fetch(', src)
        self.assertIn('rtc_get_time(', src)


if __name__ == "__main__":
    unittest.main()
