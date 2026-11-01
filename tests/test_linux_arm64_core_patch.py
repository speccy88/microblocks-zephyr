"""Pinned-source, native callback, and moving-GC regressions for the LP64 port.

The native tests compile the actual migrated callee-resolution helper and data
primitives with the real arena/collector, and upload shift bytecode through the
linked interpreter's PTY. They do not claim hardware execution.
"""
# SPDX-License-Identifier: MPL-2.0
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import select
import struct
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
module_spec = importlib.util.spec_from_file_location('linux_arm64_patch_core', ROOT / 'linux/arm64/patch_core.py')
patch = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(patch)


def upstream(name):
    return subprocess.check_output(['git', '-c', 'safe.directory=' + str(SOURCE), '-C', str(SOURCE),
                                    'show', patch.SOURCE_COMMIT + ':vm/' + name], timeout=15).decode('utf-8')


@unittest.skipUnless((SOURCE / '.git').is_dir() and shutil.which('git'), 'requires local pinned upstream Git source; no network fetch')
class PinnedCoreMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {name: upstream(name) for name in patch.PATCHED_FILES}

    def test_reviewed_revision_prepares_and_source_changes_are_rejected(self):
        for name, source in self.original.items():
            with self.subTest(file=name):
                prepared = patch.patch_core(name, source)
                self.assertTrue(prepared.startswith('/* This Source Code Form'))
                with self.assertRaises(ValueError):
                    patch.patch_core(name, source + '\n/* source drift */\n')
                if prepared != source:
                    with self.assertRaises(ValueError):
                        patch.patch_core(name, prepared)

    def test_port_is_opt_in_and_does_not_change_other_sources(self):
        text = 'Unrelated source, including native pointers, must stay unchanged.\n'
        self.assertEqual(patch.patch_core('boardHooks.c', text), text)
        self.assertEqual(patch.patch_core('persist.c', text), text)
        for name in ('varPrims.c',):
            self.assertEqual(patch.patch_core(name, self.original[name]), self.original[name])

    @unittest.skipUnless(platform.system() == 'Linux' and shutil.which('gcc'), 'requires native LP64 Linux compiler')
    def test_native_primitive_pointer_and_chunk_dispatch_are_distinct(self):
        prepared = patch.patch_core('interp.c', self.original['interp.c'])
        begin = prepared.index('typedef struct {\n\tPrimitiveFunction primitive;')
        end = prepared.index('// Interpreter\n', begin)
        helper = prepared[begin:end]
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t OBJ;
typedef OBJ (*PrimitiveFunction)(int, OBJ *);
enum { primitiveNotImplemented = 1 };
static int error;
static OBJ answer(int count, OBJ *args) { assert(count == 1); return args[0] + 1; }
static PrimitiveFunction findPrimitive(char *name) { return strcmp(name, "[test:answer]") ? NULL : answer; }
static int chunkIndexForFunction(char *name) { return strcmp(name, "function") ? -1 : 254; }
static OBJ fail(int code) { error = code; return 0; }
''' + helper + r'''
int main(void) {
    _Static_assert(sizeof(PrimitiveFunction) > sizeof(OBJ), "LP64 native function must not fit in a VM field");
    NativeCallee primitive = findCallee("[test:answer]");
    OBJ value = 41;
    assert(primitive.primitive != NULL && primitive.chunkIndex == -1);
    assert(primitive.primitive(1, &value) == 42 && error == 0);
    NativeCallee function = findCallee("function");
    assert(function.primitive == NULL && function.chunkIndex == 254 && error == 0);
    NativeCallee absent = findCallee("missing");
    assert(absent.primitive == NULL && absent.chunkIndex == -1 && error == primitiveNotImplemented);
    puts("native-pointer-call=42 chunk=254 missing=refused");
    return 0;
}
'''
        parent = ROOT / 'build-artifacts/core-callee-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            work = Path(directory)
            (work / 'callee.c').write_text(program, encoding='utf-8', newline='\n')
            build = subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                                    '-fsanitize=undefined', 'callee.c', '-o', 'callee'], cwd=work, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            execution = subprocess.run([str(work / 'callee')], capture_output=True, text=True, timeout=5)
            self.assertEqual(execution.returncode, 0, execution.stdout + execution.stderr)
            self.assertEqual(execution.stdout.strip(), 'native-pointer-call=42 chunk=254 missing=refused')
            self.assertEqual(execution.stderr, '')

    @unittest.skipUnless(platform.system() == 'Linux' and shutil.which('gcc'), 'requires native LP64 Linux compiler and PTY')
    def test_real_interpreter_shifts_are_defined_and_invalid_counts_are_vm_errors(self):
        # Build the actual pinned interpreter and its headless platform, then
        # upload/report real bytecode through its PTY. Only expected results use
        # Python integers; no copied opcode implementation stands in for the VM.
        with tempfile.TemporaryDirectory(prefix='smallvm-core-shifts-') as directory:
            work = Path(directory)
            build = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'),
                                    '--upstream', str(SOURCE), '--output', str(work / 'build'), '--sanitize'],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            data = work / 'data'
            info = data / 'pty.json'
            process = subprocess.Popen([str(work / 'build/smallvm'), '--data-dir', str(data),
                                        '--pty-info', str(info)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            descriptor = None
            incoming = bytearray()
            try:
                deadline = time.monotonic() + 5
                while not info.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(info.exists(), 'runtime did not create PTY discovery file')
                descriptor = os.open(json.loads(info.read_text())['pty'], os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

                def send(packet):
                    self.assertEqual(os.write(descriptor, packet), len(packet))

                def wait_for(kinds, expected_index=None):
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        while incoming:
                            self.assertIn(incoming[0], (250, 251), 'invalid VM output framing')
                            if incoming[0] == 250:
                                if len(incoming) < 3:
                                    break
                                size, payload = 3, b''
                            else:
                                if len(incoming) < 5:
                                    break
                                size = 5 + int.from_bytes(incoming[3:5], 'little')
                                if len(incoming) < size:
                                    break
                                payload = bytes(incoming[5:size])
                            kind, index = incoming[1:3]
                            del incoming[:size]
                            if kind in kinds and (expected_index is None or index == expected_index):
                                return kind, index, payload
                        ready, _, _ = select.select([descriptor], [], [], 0.02)
                        if ready:
                            incoming.extend(os.read(descriptor, 8192))
                        self.assertIsNone(process.poll(), 'runtime exited during a shift')
                    self.fail('timed out waiting for VM message ' + repr(kinds))

                cases = [(opcode, value, count, False) for opcode in (59, 60)
                         for value in (-1073741824, -3, -1, 0, 1, 1073741823) for count in (0, 1, 30, 31)]
                cases += [(opcode, -3, count, True) for opcode in (59, 60) for count in (-1, 32, 1000)]
                for opcode, value, count, invalid in cases:
                    with self.subTest(opcode=opcode, value=value, count=count):
                        def push(number):
                            return b'\x04\x00' + struct.pack('<I', ((number << 1) | 1) & 0xFFFFFFFF)

                        # The footer is the pinned IDE's empty metadata form.
                        code = (b'\x09\x00' + push(value) + push(count) + bytes((opcode, 2, 35, 0)) +
                                b'\x7f\x00\xf0\x00' + b'\x00' * 6)
                        body = b'\x02' + code + b'\xfe'  # reporter chunk + message terminator
                        send(bytes((251, 32, 0)) + struct.pack('<H', len(body)) + body)
                        send(bytes((250, 26, 201)))
                        self.assertEqual(wait_for({26}, 201)[:2], (26, 201))
                        send(bytes((250, 3, 0)))
                        kind, index, payload = wait_for({18, 19})
                        self.assertEqual(index, 0)
                        if invalid:
                            self.assertEqual(kind, 19, 'invalid count must fail the task')
                            self.assertEqual(payload[0], 32, 'existing argIndexOutOfRange VM error')
                        else:
                            self.assertEqual(kind, 18, 'valid shift must return a value')
                            self.assertEqual(len(payload), 5)
                            self.assertEqual(payload[0], 1, 'integer return value')
                            expected = value >> count
                            if opcode == 59:
                                expected = (value << count) & 0x7FFFFFFF
                                if expected & 0x40000000:
                                    expected -= 0x80000000
                            self.assertEqual(struct.unpack('<i', payload[1:])[0], expected)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                if process.poll() is None:
                    process.terminate()
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, stdout + stderr)
                self.assertEqual(stderr, '', 'ASan/UBSan or runtime diagnostics')

    @unittest.skipUnless(platform.system() == 'Linux' and shutil.which('gcc'), 'requires native LP64 Linux compiler')
    def test_real_data_primitives_keep_roots_and_native_views_valid_across_gc(self):
        program = r'''
#include "mem.h"
#include "interp.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
OBJ vars[MAX_VARS];
OBJ lastBroadcast;
Task tasks[MAX_TASKS];
int taskCount;
static int error, collections;
OBJ fail(uint8 code) { error = code; return falseObj; }
int failure(void) { return error != 0; }
void outputString(const char *text) { if (!strncmp(text, "GC took ", 8)) collections++; }
void captureIncomingBytes(void) { }
void updateMicrobitDisplay(void) { }
uint32 microsecs(void) { static uint32 ticks; return ++ticks; }
void addPrimitiveSet(PrimitiveSetIndex index, const char *name, int count, PrimEntry *entries) {
    (void)index; (void)name; (void)count; (void)entries;
}
extern OBJ primSplit(int, OBJ *);
extern OBJ primAsByteArray(int, OBJ *);
extern OBJ primCopyFromTo(int, OBJ *);
extern OBJ primJoinStrings(int, OBJ *);
extern OBJ primRange(int, OBJ *);
static void fresh(void) {
    memset(tasks, 0, sizeof(tasks)); taskCount = 0; memClear(); error = collections = 0;
    assert(newObj(ByteArrayType, 1000, 0)); /* unrooted prefix guarantees movement */
}
static void reserve(int available) {
    int count = wordsFree() - available - 2;
    assert(count > 0 && newObj(ByteArrayType, count, 0));
    assert(wordsFree() == available);
}
static void string_equals(OBJ value, const char *expected) {
    assert(IS_TYPE(value, StringType)); assert(!strcmp(obj2str(value), expected));
}
int main(void) {
    memInit();
    fresh();
    vars[0] = newStringFromBytes("α||bravo||42||", 15);
    vars[1] = newStringFromBytes("||", 2); vars[2] = trueObj;
    OBJ old_source = vars[0]; reserve(8);
    vars[3] = primSplit(3, vars);
    assert(!error && collections > 0 && vars[0] < old_source);
    assert(obj2int(FIELD(vars[3], 0)) == 4);
    string_equals(FIELD(vars[3], 1), "α"); string_equals(FIELD(vars[3], 2), "bravo");
    assert(FIELD(vars[3], 3) == int2obj(42)); string_equals(FIELD(vars[3], 4), "");

    fresh(); vars[0] = newStringFromBytes("é水!", 6); vars[1] = newString(0); vars[2] = falseObj;
    old_source = vars[0]; reserve(7); vars[3] = primSplit(3, vars);
    assert(!error && collections > 0 && vars[0] < old_source);
    assert(obj2int(FIELD(vars[3], 0)) == 3);
    string_equals(FIELD(vars[3], 1), "é"); string_equals(FIELD(vars[3], 2), "水"); string_equals(FIELD(vars[3], 3), "!");

    fresh(); vars[0] = newStringFromBytes("é水!", 6); old_source = vars[0]; reserve(0);
    vars[1] = charAt(vars[0], 2);
    assert(!error && collections > 0 && vars[0] < old_source); string_equals(vars[1], "水");

    fresh(); vars[0] = int2obj(2); vars[1] = newStringFromBytes("é水!", 6); reserve(0);
    vars[2] = primAt(2, vars); assert(!error && collections > 0); string_equals(vars[2], "水");

    fresh(); vars[0] = newObj(ByteArrayType, 4, 0); setByteCountAdjust(vars[0], 16);
    for (unsigned i = 0; i < 16; ++i) ((uint8 *)&FIELD(vars[0], 0))[i] = (uint8)i;
    vars[1] = int2obj(3); vars[2] = int2obj(9); old_source = vars[0]; reserve(0);
    vars[3] = primCopyFromTo(3, vars);
    assert(!error && collections > 0 && vars[0] < old_source && BYTES(vars[3]) == 7);
    for (unsigned i = 0; i < 7; ++i) assert(((uint8 *)&FIELD(vars[3], 0))[i] == i + 2);

    fresh(); vars[0] = newStringFromBytes("é水!", 6); old_source = vars[0]; reserve(0);
    vars[1] = primAsByteArray(1, vars);
    assert(!error && collections > 0 && vars[0] < old_source && BYTES(vars[1]) == 6);
    assert(!memcmp(&FIELD(vars[1], 0), "é水!", 6));

    fresh(); vars[0] = newObj(ListType, 4, zeroObj); FIELD(vars[0], 0) = int2obj(3);
    OBJ item = newStringFromBytes("é", 2); FIELD(vars[0], 1) = item;
    item = newStringFromBytes("水", 3); FIELD(vars[0], 2) = item; FIELD(vars[0], 3) = int2obj(-42);
    vars[1] = newStringFromBytes("/", 1); reserve(0); vars[2] = primJoinStrings(2, vars);
    assert(!error && collections > 0); string_equals(vars[2], "é/水/-42");

    fresh(); vars[0] = int2obj(-1073741824); vars[1] = int2obj(1073741823);
    assert(primRange(2, vars) == falseObj && error == arraySizeError);
    smallvmArenaDestroy();
    puts("split/character/byte-copy/join GC regressions passed; full-range allocation refused");
    return 0;
}
'''
        parent = ROOT / 'build-artifacts/core-data-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            work = Path(directory)
            for name in ('mem.h', 'mem.c', 'arena.h', 'arena.c'):
                shutil.copyfile(ROOT / 'linux/arm64/runtime' / name, work / name)
            (work / 'interp.h').write_text(patch.patch_core('interp.h', self.original['interp.h']), encoding='utf-8', newline='\n')
            (work / 'boardHooks.h').write_text(upstream('boardHooks.h'), encoding='utf-8', newline='\n')
            (work / 'persist.h').write_text(upstream('persist.h'), encoding='utf-8', newline='\n')
            (work / 'dataPrims.c').write_text(patch.patch_core('dataPrims.c', self.original['dataPrims.c']), encoding='utf-8', newline='\n')
            (work / 'primitive-gc.c').write_text(program, encoding='utf-8', newline='\n')
            build = subprocess.run(['gcc', '-std=c11', '-O1', '-g', '-D_DEFAULT_SOURCE', '-DSMALLVM_LINUX_ARM64=1',
                                    '-Wall', '-Wextra', '-Werror=pointer-to-int-cast', '-Werror=int-to-pointer-cast',
                                    '-Werror=incompatible-pointer-types', '-Werror=int-conversion',
                                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I.',
                                    'primitive-gc.c', 'dataPrims.c', 'mem.c', 'arena.c', '-o', 'primitive-gc'],
                                   cwd=work, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            execution = subprocess.run([str(work / 'primitive-gc')], capture_output=True, text=True, timeout=15)
            self.assertEqual(execution.returncode, 0, execution.stdout + execution.stderr)
            self.assertIn('GC regressions passed', execution.stdout)
            self.assertEqual(execution.stderr, '')


if __name__ == '__main__':
    unittest.main()
