#!/usr/bin/env python3
"""Check official Eagle schematic pin numbers against physical PCB pads.

Reads external Adafruit design references; never copies designs or uses hardware.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def audit(schematic, pcb):
    manifest = json.loads((Path(__file__).resolve().parents[1]/
                          'boards/adafruit_fruit_jam/hardware.json').read_text())
    digests = {name: hashlib.sha256(path.read_bytes()).hexdigest()
               for name, path in [('schematic', schematic), ('pcb', pcb)]}
    for name, digest in digests.items():
        if digest != manifest[name+'_sha256']:
            raise ValueError('Unreviewed '+name+' revision')
    sch, brd = ET.parse(schematic).getroot(), ET.parse(pcb).getroot()
    nets = {}
    for net in sch.findall('.//net'):
        nets.setdefault(net.attrib['name'], set()).update(
            (ref.attrib['part'], ref.attrib['gate'], ref.attrib['pin'])
            for ref in net.findall('.//pinref'))
    expected = {'1': 'SWCLK', '2': 'GND', '3': 'SWDIO'}
    part = sch.find('.//parts/part[@name="DEBUG"]')
    library = sch.find('.//libraries/library[@name="'+part.attrib['library']+'"]')
    ds = library.find('./devicesets/deviceset[@name="'+part.attrib['deviceset']+'"]')
    dev = ds.find('./devices/device[@name="'+part.attrib['device']+'"]')
    mapping = {c.attrib['pin']: c.attrib['pad'] for c in dev.findall('./connects/connect')
               if c.attrib['gate'] == 'G$1'}
    pads = {}
    for signal in brd.findall('.//signals/signal'):
        for ref in signal.findall('contactref'):
            if ref.attrib['element'] == 'DEBUG': pads[ref.attrib['pad']] = signal.attrib['name']
    for pin, net in expected.items():
        assert ('DEBUG', 'G$1', pin) in nets[net]
        assert mapping[pin] == pin and pads[pin] == net
    assert ('JP3', 'A', '26') in nets['!RESET']
    assert ('X4', 'G$1', '/RUN') in nets['!RESET']
    run_signal = brd.find('.//signals/signal[@name="!RESET"]')
    assert run_signal.find('./contactref[@element="JP3"][@pad="26"]') is not None
    assert ('R6', 'G$1', '1') in nets['PSRAM_CS']
    assert ('R6', 'G$1', '2') in nets['3.3V']
    header = {}
    for net, refs in nets.items():
        for part, gate, pin in refs:
            match = re.search(r'(?:^|/)GPIO(\d+)(?:/|$)', pin) if part == 'X4' else None
            if match:
                gpio = int(match.group(1))
                if gpio in manifest['extension_gpio_allowlist']:
                    header[str(gpio)] = {'net': net, 'JP3_pads': sorted(
                        int(p) for part, gate, p in refs if part == 'JP3')}
    assert len(header) == len(manifest['extension_gpio_allowlist'])
    return dict(result='PASS', scope='Source schematic/PCB connectivity only',
        schematic_commit=manifest['schematic_commit'], sha256=digests,
        debug_symbol_pins=expected, debug_physical_pads={p: pads[p] for p in expected},
        main_reset='JP3 pad26 / RP2350 RUN',
        unused_psram_cs_pullup='R6 to 3.3V; no need to drive GPIO47 while PSRAM is unused',
        extension_gpio_header=header, physical_tested=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schematic', required=True, type=Path)
    parser.add_argument('--pcb', required=True, type=Path)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    report = audit(args.schematic, args.pcb)
    text = json.dumps(report, indent=2)+'\n'
    if args.evidence: args.evidence.write_text(text, encoding='utf-8', newline='\n')
    print(text, end='')
