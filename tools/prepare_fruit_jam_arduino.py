#!/usr/bin/env python3
"""Prepare an isolated pinned ArduinoCore-Zephyr module for Fruit Jam.

Never modifies the supplied checkout. No network fetch, build or board access.
The real upstream core/API remain linked; RP2350 pinmux changes are per pin,
without repeating a device initialization which resets the entire ADC/PWM.
"""
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import yaml

REVISION = 'af5b8610f9be6d7b962e2ba6dd8e6859697c44ff'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def prepare(source, output):
    source, output = source.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError('Output must be a new directory outside the supplied checkout')
    if git(source, 'rev-parse', 'HEAD').decode().strip() != REVISION:
        raise ValueError('Unexpected ArduinoCore-Zephyr revision')
    # Clone from local object storage, not its network origin. No credentials
    # are copied. --no-hardlinks preserves independent output ownership.
    subprocess.run(['git', 'clone', '--no-hardlinks', '--no-checkout', '--',
                    str(source), str(output)], check=True)
    subprocess.run(['git', '-C', str(output), 'checkout', '--detach', REVISION], check=True)
    metadata = yaml.safe_load((output/'zephyr/module.yml').read_text())
    for blob in metadata.get('blobs', []):
        rel = Path(blob['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Unsafe API blob path')
        original = source/'zephyr/blobs'/rel
        if hashlib.sha256(original.read_bytes()).hexdigest() != blob['sha256']:
            raise ValueError('Missing or changed verified API blob: '+str(rel))
        target = output/'zephyr/blobs'/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    subprocess.run([sys.executable, str(Path(__file__).with_name('prepare_arduino.py')),
                    str(output)], check=True)
    path = output/'cores/arduino/zephyrCommon.cpp'
    text = path.read_text(encoding='utf-8')
    anchor = '#include "wiring_private.h"'
    if text.count(anchor) != 1:
        raise ValueError('Unexpected core include anchor')
    text = text.replace(anchor, anchor + '''
#if defined(CONFIG_BOARD_ADAFRUIT_FRUIT_JAM)
#include <hardware/gpio.h>
#include <hardware/adc.h>
#endif
''')
    anchor = '\t\t\tdev->ops.init(dev);'
    if text.count(anchor) != 1:
        raise ValueError('Unexpected core pinmux anchor')
    text = text.replace(anchor, '''#if defined(CONFIG_BOARD_ADAFRUIT_FRUIT_JAM)
            // The RP2350 drivers reset whole peripherals in init(). Restore
            // only this pin; preserve other PWM channels and ADC IRQ state.
            unsigned gpio = arduino_pins[pin].pin;
            if (arduino_pins[pin].port == DEVICE_DT_GET(DT_NODELABEL(gpio0_hi))) gpio += 32;
            if (dev == DEVICE_DT_GET(DT_NODELABEL(adc))) adc_gpio_init(gpio);
            else if (dev == DEVICE_DT_GET(DT_NODELABEL(pwm))) gpio_set_function(gpio, GPIO_FUNC_PWM);
#else
            dev->ops.init(dev);
#endif''')
    path.write_text(text, encoding='utf-8', newline='\n')
    variant = Path(__file__).resolve().parents[1]/'boards/adafruit_fruit_jam/arduino/variant.h'
    target = output/'variants/adafruit_fruit_jam/variant.h'
    if target.exists():
        raise ValueError('Pinned upstream unexpectedly already contains a Fruit Jam variant')
    target.parent.mkdir(parents=True)
    shutil.copyfile(variant, target)
    report = dict(repository='https://github.com/zephyrproject-rtos/arduino-core-zephyr',
        revision=REVISION, board='adafruit_fruit_jam',
        variant_sha256=hashlib.sha256(variant.read_bytes()).hexdigest(),
        core_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        changes=['Existing reviewed Wire fixes', 'Safe extension-only variant',
                 'RP2350 per-pin ADC/PWM mux, without device reinitialization'],
        upstream_checkout_modified=False, compiled=False, physical_tested=False)
    (output/'fruitjam-provenance.json').write_text(json.dumps(report, indent=2)+'\n',
                                               encoding='utf-8', newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), indent=2))
