#!/usr/bin/env python3
"""Execute the real local SmallVM binary through its PTY, never a mock interpreter.

Linux only. This script creates disposable private data directories, uploads test
programs, terminates/restarts its own child processes and checks saved code. It
does not use SSH, open physical serial ports, install services or reboot a host.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import signal
import stat
import struct
import subprocess
import tempfile
import time
import tty
import zlib


def op(code, arg=0):
    return code | ((arg & 255) << 8)


def words(values):
    return struct.pack('<' + 'H' * len(values), *values)


class Wire:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        tty.setraw(self.fd)
        self.buffer = bytearray()
        self.events = []

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def write(self, data):
        data = memoryview(data)
        until = time.monotonic() + 5
        while data:
            if time.monotonic() >= until:
                raise TimeoutError('PTY write did not complete')
            if not select.select([], [self.fd], [], .1)[1]:
                continue
            try:
                count = os.write(self.fd, data)
            except BlockingIOError:
                continue
            if count <= 0:
                raise RuntimeError('PTY closed during write')
            data = data[count:]

    def short(self, kind, index=0):
        self.write(bytes([250, kind, index]))

    def long(self, kind, index=0, payload=b''):
        body = payload + b'\xfe'
        self.write(bytes([251, kind, index]) + struct.pack('<H', len(body)) + body)

    def pump(self, timeout=.1):
        if not select.select([self.fd], [], [], timeout)[0]:
            return
        data = os.read(self.fd, 4096)
        if not data:
            raise RuntimeError('VM closed PTY')
        self.buffer.extend(data)
        if len(self.buffer) > 65536 or len(self.events) > 10000:
            raise RuntimeError('VM output exceeded test bounds')
        while self.buffer:
            if self.buffer[0] == 250:
                if len(self.buffer) < 3:
                    return
                self.events.append((self.buffer[1], self.buffer[2], b''))
                del self.buffer[:3]
            elif self.buffer[0] == 251:
                if len(self.buffer) < 5:
                    return
                size = int.from_bytes(self.buffer[3:5], 'little')
                if len(self.buffer) < 5 + size:
                    return
                self.events.append((self.buffer[1], self.buffer[2], bytes(self.buffer[5:5 + size])))
                del self.buffer[:5 + size]
            else:
                raise RuntimeError(f'Unframed VM output: {self.buffer[:16].hex()}')

    def wait(self, predicate, after=0, timeout=5):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            for event in self.events[after:]:
                if event[0] == 19:
                    raise RuntimeError(f'Actual interpreter task error: {event[2].hex()}')
                if predicate(event):
                    return event
            self.pump()
        raise TimeoutError('Expected official SmallVM message was not received')

    def ping(self, index=73):
        start = len(self.events)
        self.short(26, index)
        self.wait(lambda e: e[:2] == (26, index), start)

    def crc(self, chunk):
        start = len(self.events)
        self.short(11, chunk)
        return int.from_bytes(self.wait(lambda e: e[:2] == (23, chunk), start)[2], 'little')

    def upload(self, chunk, code, kind=1, fragmented=False):
        assert len(code) % 4 == 0
        body = bytes([kind]) + code + b'\xfe'
        packet = bytes([251, 32, chunk]) + struct.pack('<H', len(body)) + body
        start = len(self.events)
        if fragmented:
            for at in range(0, len(packet), 17):
                self.write(packet[at:at + 17])
                time.sleep(.002)
        else:
            self.write(packet)
        actual = int.from_bytes(self.wait(lambda e: e[:2] == (23, chunk), start)[2], 'little')
        assert actual == zlib.crc32(code), (actual, zlib.crc32(code))
        return actual

    def reporter(self, chunk):
        start = len(self.events)
        self.short(3, chunk)
        body = self.wait(lambda e: e[:2] == (18, chunk), start)[2]
        if body[0] == 1:
            return int.from_bytes(body[1:5], 'little', signed=True)
        if body[0] == 2:
            return body[1:].decode('utf-8')
        if body[0] == 3:
            return bool(body[1])
        raise RuntimeError('Unexpected reporter result type')

    def variable(self, index):
        start = len(self.events)
        self.short(7, index)
        body = self.wait(lambda e: e[:2] == (21, index), start)[2]
        assert body[0] == 1 and len(body) == 5
        return int.from_bytes(body[1:], 'little', signed=True)


class Runtime:
    def __init__(self, binary, data, index):
        self.data = data
        self.info = data / f'test-pty-{index}.json'
        self.log = open(data / f'process-{index}.log', 'w+', encoding='utf-8')
        self.process = subprocess.Popen([str(binary), '--data-dir', str(data), '--pty-info', str(self.info)], stdout=self.log, stderr=subprocess.STDOUT)
        self.wire = None
        try:
            until = time.monotonic() + 5
            while not self.info.exists():
                if self.process.poll() is not None or time.monotonic() > until:
                    self.log.flush()
                    self.log.seek(0)
                    raise RuntimeError('Real VM did not become ready: ' + self.log.read())
                time.sleep(.01)
            metadata = json.loads(self.info.read_text())
            assert metadata['pid'] == self.process.pid and metadata['transport'] == 'pty'
            assert metadata['network_listener'] is False
            assert stat.S_IMODE(self.info.stat().st_mode) == 0o600
            self.wire = Wire(metadata['pty'])
            self.wire.ping()
        except BaseException:
            if self.wire:
                self.wire.close()
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            self.log.close()
            raise

    def stop(self, abrupt=False):
        if self.wire:
            self.wire.close()
            self.wire = None
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGKILL if abrupt else signal.SIGTERM)
            self.process.wait(timeout=5)
        if not abrupt:
            assert not self.info.exists(), 'Graceful exit left stale PTY discovery info'
        self.log.close()


def idle_metrics(process):
    """Bounded measurements of this runner's own still-running child only."""
    proc = Path('/proc') / str(process.pid)
    ticks_per_second = os.sysconf('SC_CLK_TCK')

    def sample():
        if process.poll() is not None:
            raise RuntimeError('Test child exited before idle resource measurement')
        # comm may contain spaces/parentheses; fields after its final ')' start
        # at field 3 (state), so utime/stime (14/15) are indices 11/12 here.
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        ticks = int(fields[11]) + int(fields[12])
        status = {}
        for line in (proc / 'status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                key, value, unit = line.split()
                if unit != 'kB':
                    raise RuntimeError('Unexpected Linux process-memory unit')
                status[key.rstrip(':')] = int(value) * 1024
        return ticks, status['VmRSS'], status['VmHWM']

    first = sample()
    started = time.monotonic()
    time.sleep(.5)
    elapsed = time.monotonic() - started
    last = sample()
    delta = last[0] - first[0]
    assert delta >= 0 and process.poll() is None
    return {
        'scope': 'this runner child process, idle before test-program uploads',
        'host_architecture': platform.machine(),
        'sample_seconds': round(elapsed, 6),
        'clock_ticks_per_second': ticks_per_second,
        'cpu_ticks_delta': delta,
        'cpu_percent_one_core': round(100 * delta / ticks_per_second / elapsed, 4),
        'rss_before_bytes': first[1],
        'rss_after_bytes': last[1],
        'peak_rss_bytes': last[2],
        'instrumentation': 'not inferred; consult the binary build manifest',
        'sanitizer_caveat': 'ASan/UBSan builds add CPU and memory overhead; compare them separately from production builds.',
    }


def run(binary, repeats):
    checks = {}
    self_test = subprocess.run([str(binary), '--self-test'], capture_output=True, text=True, timeout=15, check=True)
    self_report = json.loads(self_test.stdout.strip().splitlines()[-1])
    assert self_report['result'] == 'PASS' and self_report['arithmetic'] == 12 and self_report['variable'] == 42
    assert self_report['architecture'] == platform.machine()
    checks['real_interpreter_self_test'] = self_report
    with tempfile.TemporaryDirectory(prefix='smallvm-native-protocol-') as temporary:
        base = Path(temporary)
        data = base / 'data'
        data.mkdir(mode=0o700)
        runtime = Runtime(binary, data, 1)
        try:
            vm = runtime.wire
            contender = subprocess.run([str(binary), '--data-dir', str(data)], capture_output=True, text=True, timeout=5)
            assert contender.returncode != 0 and runtime.info.exists()
            vm.ping(74)
            checks['exclusive_data_owner'] = True
            checks['idle_resources'] = idle_metrics(runtime.process)
            vm.short(14, 1)
            vm.short(15, 0)
            vm.ping(75)
            reporter = bytes([9, 0, 2, 11, 2, 15, 50, 2, 35, 0, 127, 0, 240, 0, 0, 0, 0, 0, 0, 0])
            crcs = {0: vm.upload(0, reporter, 2)}
            # The real GP IDE sends this preference even on a headless target.
            # Unsupported BLE stays off and must not poison the next VM task.
            vm.short(31, 1)
            vm.ping(83)
            assert vm.reporter(0) == 12
            vm.short(31, 0)
            checks['unsupported_ble_preference_does_not_poison_tasks'] = True
            assert [vm.reporter(0) for _ in range(repeats)] == [12] * repeats
            checks['arithmetic_executions'] = repeats
            edited = bytearray(reporter)
            edited[5] = 17
            vm.upload(0, edited, 2)
            assert vm.reporter(0) == 13
            vm.upload(0, reporter, 2)
            checks['live_edit_result'] = 13
            assignment = words([op(9), op(2, 85), op(7, 2), 0])
            crcs[1] = vm.upload(1, assignment)
            start = len(vm.events)
            vm.short(3, 1)
            vm.wait(lambda e: e[:2] == (17, 1), start)
            assert vm.variable(2) == 42
            checks['variable_readback'] = 42
            loop = words([op(9), op(2, 3), op(8, 5), op(22, -3)])
            crcs[5] = vm.upload(5, loop)
            start = len(vm.events)
            vm.short(3, 5)
            vm.wait(lambda e: e[:2] == (16, 5), start)
            time.sleep(.05)
            vm.short(4, 5)
            vm.ping(76)
            stopped = vm.variable(5)
            time.sleep(.05)
            assert stopped > 0 and vm.variable(5) == stopped
            checks['stop_and_readback'] = True
            large = words([op(21)] * 500 + [op(2, 85), op(7, 3), 0, 0, 0, 0])
            crcs[2] = vm.upload(2, large, fragmented=True)
            start = len(vm.events)
            vm.short(3, 2)
            vm.wait(lambda e: e[:2] == (17, 2), start)
            assert vm.variable(3) == 42
            checks['fragmented_upload_bytes'] = len(large) + 7
            startup = words([op(9), op(2, 85), op(7, 9), 0])
            crcs[4] = vm.upload(4, startup, kind=4)
            # Exercise actual core compaction and its staged atomic file replacement.
            vm.long(30, 2)
            vm.upload(0, edited, 2)
            vm.long(30, 3)
            vm.ping(77)
            crcs[0] = zlib.crc32(edited)
            checks['suspend_resume_and_compaction'] = True
            assert stat.S_IMODE((data / 'program.ucode').stat().st_mode) == 0o600
            runtime.stop()
            runtime = Runtime(binary, data, 2)
            vm = runtime.wire
            assert vm.reporter(0) == 13 and vm.variable(9) == 42
            for chunk, crc in crcs.items():
                assert vm.crc(chunk) == crc
            checks['graceful_restart_code_crc_and_autostart'] = True
            vm.upload(0, reporter, 2)
            runtime.stop(abrupt=True)
            runtime = Runtime(binary, data, 3)
            assert runtime.wire.reporter(0) == 12 and runtime.wire.variable(9) == 42
            checks['process_kill_after_ack_persistence'] = True
            runtime.stop()
            runtime = None
            original = (data / 'program.ucode').read_bytes()
            corruptions = [b'bad!', original[:-1], original[:4] + b'\x00\x00\xffR\xff\xff\xff\xff', original[:4] + b'\x00\x00\x0cR\xff\xff\xff\xff']
            for index, corrupt in enumerate(corruptions):
                bad_data = base / f'corrupt-{index}'
                bad_data.mkdir(mode=0o700)
                state = bad_data / 'program.ucode'
                state.write_bytes(corrupt)
                state.chmod(0o600)
                digest = hashlib.sha256(state.read_bytes()).hexdigest()
                failed = subprocess.run([str(binary), '--data-dir', str(bad_data)], capture_output=True, text=True, timeout=5)
                assert failed.returncode != 0
                assert hashlib.sha256(state.read_bytes()).hexdigest() == digest
            checks['corrupt_files_refused_and_retained'] = len(corruptions)
            sentinel = data / 'existing-info.json'
            sentinel.write_text('preserve existing user file\n')
            sentinel.chmod(0o600)
            rejected = subprocess.run([str(binary), '--data-dir', str(data), '--pty-info', str(sentinel)], capture_output=True, text=True, timeout=5)
            assert rejected.returncode != 0 and sentinel.read_text() == 'preserve existing user file\n'
            checks['existing_info_file_preserved'] = True
        finally:
            if runtime is not None:
                runtime.stop()
    return {'result': 'PASS', 'scope': 'real SmallVM v417 on local Linux PTY; no external peripheral or graphical IDE claim', 'architecture': platform.machine(), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'checks': checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--repeat', type=int, default=20)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        parser.error('Run this real-process PTY test on Linux; no simulated fallback exists')
    if not 1 <= args.repeat <= 1000:
        parser.error('--repeat must be 1..1000')
    report = run(args.binary.resolve(strict=True), args.repeat)
    text = json.dumps(report, indent=2) + '\n'
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text, encoding='utf-8', newline='\n')
    print(text, end='')


if __name__ == '__main__':
    main()
