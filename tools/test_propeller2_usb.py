#!/usr/bin/env python3
"""Bounded physical P2 test: replaces test code; no external output or firmware flash.

Requires an explicitly identified module and exact FTDI serial. --reboot
tests flash-boot persistence only after the matching image has been installed.
Smart Pin tests use only the onboard LED pin with output disabled.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import time
from pathlib import Path
import serial
from p2_serial import P2SerialVM, BOARDS, primitive, op, words


def test(port, usb_serial, board, reboot, evidence):
    report = dict(tested_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='physical USB binary protocol; input-only Smart Pin configuration',
                  module=board, checks={}, externally_measured_waveforms=False,
                  graphical_browser_test=False)
    vm = None
    try:
        vm = P2SerialVM(port, usb_serial, board)
        report.update(identity=vm.identity, version=vm.version)
        start = len(vm.events); vm.short(26, 91)
        vm.wait(lambda e: e[:2] == (26, 91), after=start)
        report['checks']['binary_ping'] = True
        vm.short(14, 1)  # authorized replacement of this P2's stored test project
        time.sleep(.2)
        reporter = bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
        vm.upload(0, reporter, 2)
        assert [vm.run_reporter(0) for _ in range(10)] == [12]*10
        report['checks']['arithmetic_runs'] = 10
        edited = bytearray(reporter); edited[5] = 17
        vm.upload(0, edited, 2); assert vm.run_reporter(0) == 13
        vm.upload(0, reporter, 2)
        report['checks']['live_edit_5_plus_8'] = 13
        print('Arithmetic and live edit PASS', flush=True)
        def call(name, *args):
            vm.upload(10, primitive(name, args), 2)
            return vm.run_reporter(10)
        assert call('p2Board') == BOARDS[board]
        report['checks']['flash_jedec_hex'] = call('p2FlashID')
        assert call('p2ClockHz') == 180000000
        report['checks']['cog'] = call('p2Cog')
        count = 40 if board == 'edge32' else 58
        assert call('p2PinCount') == count
        invalid = [-1, *range(count, 64), 64, 256, 511]
        for pin in invalid: assert call('p2PinUsable', pin) is False
        assert call('p2PinUsable', count-1) is True
        report['checks']['reserved_and_alias_pins_rejected'] = invalid
        print('Reserved pin checks PASS', flush=True)
        pin = 38 if board == 'edge32' else 56
        assert call('p2SmartPin', pin, 'count highs', 32, 0) is True
        assert call('p2PinModeHex', pin) == '0000001e'
        # Full-bit raw input mode; P_OE is clear, so no external pin is driven.
        assert call('p2SmartPinRaw', pin, '8000001e', '00000020', '00000000') is True
        assert call('p2PinModeHex', pin) == '8000001e'
        assert call('p2PinWriteX', pin, '00000040') is True
        assert call('p2PinWriteY', pin, 'deadbeef') is True
        report['checks']['input_mode_Z_hex'] = call('p2PinReadHex', pin)
        for raw in ['', '100000000', 'xyz', '00000000', '00000036']:
            assert call('p2SmartPinRaw', pin, raw, '0', '0') is False
        assert call('p2SmartPinRaw', count-1, '1000001e', '0', '0') is False
        for reserved in sorted(set(invalid)):
            assert call('p2SmartPinRaw', reserved, '1e', '20', '0') is False
        assert call('p2PinRelease', pin) is True
        assert call('p2PinModeHex', pin) == '00000000'
        report['checks']['smart_pin_input_configuration_and_full_width_hex'] = True
        print('Input-only Smart Pin configuration PASS', flush=True)
        tagged_count = 99
        stream = words([op(2,1),op(7,0),op(3,tagged_count),0,op(7,1),op(6,1),
            op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
        vm.upload(3, stream)
        start = len(vm.events); vm.short(3, 3)
        vm.wait(lambda e:e[:2] == (17,3), seconds=20, after=start)
        outputs = [int(e[2][1:]) for e in vm.events[start:] if e[:2] == (20,254)]
        assert outputs == list(range(1,51))
        report['checks']['ordered_outputs'] = 50
        large = words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0])
        vm.upload(2, large, fragmented=True)
        start = len(vm.events); vm.short(3,2)
        vm.wait(lambda e:e[:2] == (17,2), after=start)
        assert vm.variable(2) == 42
        report['checks']['fragmented_upload_bytes'] = len(large)+7
        report['checks']['maximum_upload_crc_seconds'] = round(max(vm.upload_seconds), 3)
        print('Ordered output and fragmented upload PASS', flush=True)
        for chunk in [2,3,10]: vm.short(2, chunk)
        startup = words([op(9),op(2,85),op(7,9),0])
        vm.upload(4, startup, kind=4)
        vm.upload(6, primitive('p2SmartPin', [pin, 'count highs', 32, 0]), kind=4)
        crcs = vm.all_crcs()
        report['checks']['saved_crc32'] = {str(k):f'{v:08x}' for k,v in crcs.items()}
        vm.close(); vm = None
        vm = P2SerialVM(port, usb_serial, board)
        assert vm.run_reporter(0) == 12
        report['checks']['serial_reconnect'] = True
        if reboot:
            vm.serial.dtr = True; time.sleep(.01); vm.serial.dtr = False
            vm.close(); vm = None; time.sleep(2)
            vm = P2SerialVM(port, usb_serial, board)
            assert vm.all_crcs() == crcs
            assert vm.run_reporter(0) == 12
            assert vm.variable(9) == 42
            report['checks']['reset_persistence_crc_arithmetic_and_autostart'] = True
            assert call('p2PinModeHex', pin) == '0000001e'
            report['checks']['startup_input_smart_pin_configuration_restored'] = True
            assert call('p2PinRelease', pin) is True
            vm.short(2, 10)
        report['result'] = 'PASS'
    except BaseException as error:
        report.update(result='FAIL', error=type(error).__name__+': '+str(error)); raise
    finally:
        if vm: vm.close()
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--usb-serial', required=True)
    parser.add_argument('--board', choices=BOARDS, required=True)
    parser.add_argument('--reboot', action='store_true')
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    test(args.port, args.usb_serial, args.board, args.reboot, args.evidence)
