"""Port only the reviewed v417 core to compact references on LP64 Linux.

The caller supplies a checked uint32 OBJ arena memory backend. This patch keeps
VM fields, tags, persisted words and 16-bit bytecode unchanged, and converts
native addresses at explicit O2A/A2O boundaries. Existing MCU builds do not use
this module. It deliberately rejects changed or already patched source bytes.
"""
# SPDX-License-Identifier: MPL-2.0
import hashlib

SOURCE_COMMIT = '2071df569623ba9cdcd6f8106b61796e047df38b'
SOURCE_SHA256 = {
    'interp.c': '73fe8829d0b3e7394a5660c8a433ef317e4ffb08376b6bc0b25bd2fe5404c78e',
    'interp.h': 'ff94118f0aba88500a6a3a1aaee63cedfa3e5c855735c99bc2354f9ec7eaf735',
    'runtime.c': 'd12c4c258b34555dbbf5e7e50770b4af0cec1b7ba282dadc3a6fd57002685f3b',
    'dataPrims.c': 'af314984d4b6b71b9eaff28fe0dc65d184afbcfc3d1865895580bd55c958a715',
    'varPrims.c': '45d178e6e5a3793fc71b33084b7b0922eaede739461ddd25b0f31be3a42348f9',
    'miscPrims.c': '67605b35a3d4acfdd8e59b5a543d2af10d2deca63bd44a2ebcbe898c7ca42c8b',
}
PATCHED_FILES = tuple(SOURCE_SHA256)


def replace(text, before, after, count=1):
    actual = text.count(before)
    if actual != count:
        raise ValueError(f'Unexpected v417 anchor count {actual}, expected {count}: {before[:80]!r}')
    return text.replace(before, after)


def _interpreter(text):
    # A process-static C object cannot be represented by an arena offset.
    before = '''// statically allocated object for the boardType primitive result
static struct {
\tuint32 header;
\tchar body[BOARD_TYPE_SIZE];
} boardTypeObj;

OBJ primBoardType() {
\tstrncpy(boardTypeObj.body, boardType(), BOARD_TYPE_SIZE - 1);
\tint wordCount = (strlen(boardTypeObj.body) + 4) / 4;
\tboardTypeObj.header = HEADER(StringType, wordCount);
\treturn (OBJ) &boardTypeObj;
}'''
    after = '''OBJ primBoardType() {
\tconst char *name = boardType();
\treturn newStringFromBytes(name, strnlen(name, BOARD_TYPE_SIZE - 1));
}'''
    text = replace(text, before, after)
    text = replace(text, '(uint32 *) chunks[chunkIndex].code', 'O2A(chunks[chunkIndex].code)')
    # Includes the commented debug expression, keeping it safe to re-enable.
    text = replace(text, '(int16 *) task->code', '(int16 *) O2A(task->code)', 6)
    text = replace(text, '(int16 *) (task->code + PERSISTENT_HEADER_WORDS)',
                   '(int16 *) (O2A(task->code) + PERSISTENT_HEADER_WORDS)')
    text = replace(text, '(OBJ) (ip++ + tmp)', 'A2O(ip++ + tmp)')
    text = replace(text, '(OBJ) (ip + (*ip & 0x3FF))', 'A2O(ip + (*ip & 0x3FF))', 2)
    text = replace(text, 'tempGCRoot = NULL;', 'tempGCRoot = 0;')

    # Never encode a native C function pointer in int/OBJ; a typed result keeps
    # primitive pointers entirely outside compact VM memory and chunk tags.
    before = '''static int findCallee(char *functionOrPrimitiveName) {
\t// Look for a primitive match first since that is fast
\tPrimitiveFunction f = findPrimitive(functionOrPrimitiveName);
\tif (f) return (int) f;

\t// Look for a user-defined function match (slow if no match found!)
\tint result = chunkIndexForFunction(functionOrPrimitiveName);
\tif (result >= 0) return (0xFFFFFF00 | result); // set top 24 bits to show callee is a chunk
\t// assume: result < 256 (MAX_CHUNKS) so it fits in low 8 bits

\tfail(primitiveNotImplemented);
\treturn -1;
}'''
    after = '''typedef struct {
\tPrimitiveFunction primitive;
\tint chunkIndex;
} NativeCallee;

static NativeCallee findCallee(char *functionOrPrimitiveName) {
\tNativeCallee result = {findPrimitive(functionOrPrimitiveName), -1};
\tif (result.primitive) return result;
\tresult.chunkIndex = chunkIndexForFunction(functionOrPrimitiveName);
\tif (result.chunkIndex < 0) fail(primitiveNotImplemented);
\treturn result;
}'''
    text = replace(text, before, after)
    text = replace(text, 'uint32 callee = -1;', 'NativeCallee callee = {NULL, -1};')
    text = replace(text, 'if (callee != -1) { // found a callee',
                   'if (callee.primitive || callee.chunkIndex >= 0) { // found a callee')
    text = replace(text, 'if ((callee & 0xFFFFFF00) == 0xFFFFFF00) { // callee is a MicroBlocks function (i.e. a chunk index)',
                   'if (callee.chunkIndex >= 0) { // callee is a MicroBlocks function')
    text = replace(text, 'arg = ((callee & 0xFF) << 8) | paramCount;',
                   'arg = (callee.chunkIndex << 8) | paramCount;')
    text = replace(text, 'tmpObj = ((PrimitiveFunction) callee)(paramCount, sp - paramCount); // call the primitive',
                   'tmpObj = callee.primitive(paramCount, sp - paramCount); // native pointer remains typed')

    # The encoded integer bit pattern is 32 bits even on LP64. Shift unsigned
    # values when assembling raw immediates to avoid signed-left-shift UB.
    text = replace(text, 'tmp = (*ip++ << 8) | (arg & 0xFF);',
                   'tmp = (int32_t)(((uint32) (int32_t) *ip++ << 8) | ((uint32) arg & 0xFF));')
    text = replace(text, 'tmp |= (uint16) *ip++ << 16;',
                   'tmp = (int32_t)((uint32) tmp | ((uint32) (uint16) *ip++ << 16));')
    text = replace(text, 'int2obj(evalInt(*(sp - 2)) * evalInt(*(sp - 1)))',
                   'int2obj((uint32) evalInt(*(sp - 2)) * (uint32) evalInt(*(sp - 1)))')
    text = replace(text, 'static inline OBJ primSum(int argCount, OBJ *args) {\n\tint result = 0;',
                   'static inline OBJ primSum(int argCount, OBJ *args) {\n\tuint32 result = 0;')
    text = replace(text, 'int range = (last + 1) - first; // if first == last range is 1 and first is returned\n\treturn int2obj(first + (rand() % range));',
                   'int64_t range = ((int64_t) last + 1) - first; // full signed31 range fits\n\treturn int2obj((int64_t) first + (rand() % range));')

    # Official Operators documentation specifies zero-filled left shift and
    # sign-preserving arithmetic right shift, without an out-of-range count
    # rule: https://wiki.microblocks.fun/en/reference_manual/operators
    # Define counts 0..31; reject other counts with the existing argument-range
    # error. The old C expressions had undefined behavior for those inputs,
    # rather than a portable result to preserve. Do not mask/modulo the count.
    before = '''\tbitShiftLeft_op:
\t\t*(sp - arg) = int2obj(evalInt(*(sp - 2)) << evalInt(*(sp - 1)));
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();
\tbitShiftRight_op:
\t\t*(sp - arg) = int2obj(evalInt(*(sp - 2)) >> evalInt(*(sp - 1)));
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();'''
    after = '''\tbitShiftLeft_op: {
\t\tint count = evalInt(*(sp - 1));
\t\tuint32 bits = (uint32) evalInt(*(sp - 2));
\t\tif (errorCode) goto error;
\t\tif (count < 0 || count > 31) { fail(argIndexOutOfRange); goto error; }
\t\t*(sp - arg) = int2obj(bits << count);
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();
\t}
\tbitShiftRight_op: {
\t\tint count = evalInt(*(sp - 1));
\t\tint value = evalInt(*(sp - 2));
\t\tif (errorCode) goto error;
\t\tif (count < 0 || count > 31) { fail(argIndexOutOfRange); goto error; }
\t\tuint32 bits = (uint32) value >> count;
\t\t// Explicit sign extension avoids implementation-defined signed shift.
\t\tif (value < 0 && count) bits |= UINT32_MAX << (32 - count);
\t\t*(sp - arg) = int2obj(bits);
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();
\t}'''
    text = replace(text, before, after)

    # evalInt now guarantees signed31 inputs. Evaluate both before arithmetic so
    # conversion failures survive the divide/modulo zero checks. Widen the
    # division itself as a second guard against INT32_MIN / -1 C overflow.
    before = '''\tdivide_op:
\t\ttmp = evalInt(*(sp - 1));
\t\t*(sp - arg) = ((0 == tmp) ? fail(zeroDivide) : int2obj(evalInt(*(sp - 2)) / tmp));
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();'''
    after = '''\tdivide_op: {
\t\tif (arg != 2) { fail(notEnoughArguments); goto error; }
\t\tint divisor = evalInt(*(sp - 1));
\t\tint64_t dividend = evalInt(*(sp - 2));
\t\tif (errorCode) goto error;
\t\t*(sp - arg) = divisor ? int2obj(dividend / divisor) : fail(zeroDivide);
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();
\t}'''
    text = replace(text, before, after)
    text = replace(text, 'static OBJ primModulo(int argCount, OBJ *args) {\n\tint n',
                   'static OBJ primModulo(int argCount, OBJ *args) {\n\tif (argCount != 2) return fail(notEnoughArguments);\n\tint n')
    text = replace(text, '\tint modulus = evalInt(args[1]);\n\tif (0 == modulus)',
                   '\tint modulus = evalInt(args[1]);\n\tif (failure()) return falseObj;\n\tif (0 == modulus)')
    before = '''\tlongMultiply_op:
\t\t{
\t\t\tlong long product = (long long) (evalInt(*(sp - 3))) * (long long) (evalInt(*(sp - 2)));
\t\t\ttmp = (int) ((product >> (evalInt(*(sp - 1)))) & 0xFFFFFFFF);
\t\t\t*(sp - arg) = int2obj(tmp);
\t\t}
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();'''
    after = '''\tlongMultiply_op: {
\t\tif (arg != 3) { fail(notEnoughArguments); goto error; }
\t\tint count = evalInt(*(sp - 1));
\t\tint64_t left = evalInt(*(sp - 3)), right = evalInt(*(sp - 2));
\t\tif (errorCode) goto error;
\t\tif (count < 0 || count > 63) { fail(argIndexOutOfRange); goto error; }
\t\tint64_t product = left * right; // signed31 product fits in signed64
\t\tuint64_t bits = (uint64_t) product >> count;
\t\tif (product < 0 && count) bits |= UINT64_MAX << (64 - count);
\t\t*(sp - arg) = int2obj((uint32) bits);
\t\tPOP_ARGS_REPORTER();
\t\tDISPATCH();
\t}'''
    text = replace(text, before, after)

    # Cooperative bounded scheduling matches the existing audited MCU port.
    text = replace(text, '\tif (errorCode) goto error; \\\n',
                   '\tif (errorCode) goto error; \\\n\tif (!instructionBudget--) goto suspend; \\\n')
    text = replace(text, 'static void runTask(Task *task) {',
                   'static void runTask(Task *task) {\n\tunsigned instructionBudget = 256;')
    for opcode, condition in [('i2cSet', 'arg != 3'), ('i2cGet', 'arg != 2'),
                              ('spiSend', 'arg != 1'), ('spiRecv', 'arg != 0'),
                              ('analogWrite', 'arg != 2'), ('analogRead', 'arg < 1 || arg > 2'),
                              ('digitalWrite', 'arg != 2'), ('digitalRead', 'arg < 1 || arg > 2')]:
        anchor = '\t' + opcode + '_op:\n'
        text = replace(text, anchor, anchor + '\t\tif (' + condition + ') { fail(notEnoughArguments); goto error; }\n')
    text = replace(text, 'void vmLoop() {', 'void vmSlice(unsigned cycles) {')
    text = replace(text, '\tint currentTaskIndex = 0;\n\tint count = 0;\n\twhile (true) {',
                   '\tstatic int currentTaskIndex = 0;\n\tstatic int count = 0;\n\twhile (cycles--) {')
    return replace(text, '#endif // not __EMSCRIPTEN__',
                   'void vmLoop() { while (true) vmSlice(1); }\n\n#endif // not __EMSCRIPTEN__')


def _runtime(text):
    # v417 calls display-off from protocol erase/reset cleanup, outside a task.
    # The headless hardware stub would leave primitiveNotImplemented pending
    # for the next unrelated script. Skip only these three internal cleanups;
    # explicit display bytecode still reaches the unsupported hardware stub.
    text = replace(text, 'primMBDisplayOff(0, NULL)',
                   '((void) 0) /* headless protocol display cleanup */', 3)
    # Cancel only the local bounded RPC waits. This cannot roll back a request
    # already accepted by robotd, and does not replace the robot's own controls.
    text = replace(text, 'static void stopAllTasks() {',
                   'static void stopAllTasks() {\n\tlinuxMicroduckCancelPending();')
    text = replace(text, 'void stopAllTasksButThis(Task *thisTask) {',
                   'void stopAllTasksButThis(Task *thisTask) {\n\tlinuxMicroduckCancelPending();')
    text = replace(text, 'tempGCRoot = NULL;', 'tempGCRoot = 0;')
    text = replace(text, 'if (NULL == chunks[chunkIndex].code)', 'if (0 == chunks[chunkIndex].code)')
    text = replace(text, '(int16 *) (chunks[chunkIndex].code + PERSISTENT_HEADER_WORDS)',
                   '(int16 *) (O2A(chunks[chunkIndex].code) + PERSISTENT_HEADER_WORDS)')
    text = replace(text, 'obj2str((OBJ) (code + *(code + 1) + 1))',
                   'obj2str(A2O(code + *(code + 1) + 1))')
    text = replace(text, 'chunks[chunkIndex].code = persistentChunk;',
                   'chunks[chunkIndex].code = persistentChunk ? A2O(persistentChunk) : 0;')
    text = replace(text, 'chunks[chunkIndex].code = NULL;', 'chunks[chunkIndex].code = 0;')
    text = replace(text, 'if (NULL == code)', 'if (0 == code)')
    text = replace(text, 'int wordCount = *(code + 1);', 'int wordCount = O2A(code)[1];', 2)
    text = replace(text, 'int chunkWords = *(code + 1);', 'int chunkWords = O2A(code)[1];')
    text = replace(text, '(code + PERSISTENT_HEADER_WORDS)', '(O2A(code) + PERSISTENT_HEADER_WORDS)', 3)
    # Named-primitive strings are supplied by compiled programs; bound the native
    # parser before copying to fixed C arrays.
    text = replace(text, 'if (count < 1) return NULL;', 'if (count < 1 || count >= 100) return NULL;', 2)
    text = replace(text, 'int type = data[0];\n\t\tswitch (type)',
                   'if (byteCount < 1) return;\n\t\tint type = data[0];\n\t\tswitch (type)')
    text = replace(text, 'case 1: // integer\n\t\t\tvars[varID] = int2obj((data[4] << 24) | (data[3] << 16) | (data[2] << 8) | data[1]);',
                   'case 1: // integer\n\t\t\tif (byteCount != 5) return;\n\t\t\tvars[varID] = int2obj(((uint32) data[4] << 24) | ((uint32) data[3] << 16) | ((uint32) data[2] << 8) | data[1]);')
    text = replace(text, 'case 3: // boolean\n\t\t\tvars[varID] = data[1] ? trueObj : falseObj;',
                   'case 3: // boolean\n\t\t\tif (byteCount != 2) return;\n\t\t\tvars[varID] = data[1] ? trueObj : falseObj;')

    # Recover incomplete byte streams without confusing their timeout with IDE
    # liveness. Reuses the repository's already exercised framing policy.
    text = replace(text, 'uint32 lastRcvTime = 0;', 'uint32 lastRcvTime = 0;\nstatic uint32 lastByteTime = 0;')
    text = replace(text, '\tuint32 usecs = microsecs();\n\tif (usecs < lastRcvTime) lastRcvTime = 0; // clock wrap\n\treturn (usecs - lastRcvTime) > 20000;',
                   '\treturn (uint32)(microsecs() - lastByteTime) > 250000;')
    text = replace(text, 'void captureIncomingBytes() {',
                   'static void expirePartialHead(void) {\n'
                   '\tif (!rcvByteCount || !receiveTimeout()) return;\n'
                   '\tint partial = (rcvBuf[0] == 250 && rcvByteCount < 3);\n'
                   '\tif (rcvBuf[0] == 251) partial = rcvByteCount < 5 ||\n'
                   '\t\t(rcvByteCount < 5 + ((rcvBuf[4] << 8) | rcvBuf[3]));\n'
                   '\tif (partial) rcvByteCount = 0;\n}\n\n'
                   'void captureIncomingBytes() {\n\texpirePartialHead();')
    text = replace(text, 'int bytesRead = recvBytes(&rcvBuf[rcvByteCount], RCVBUF_SIZE - rcvByteCount);',
                   'int bytesRead = recvBytes(&rcvBuf[rcvByteCount], RCVBUF_SIZE - rcvByteCount);\n'
                   '\tif (bytesRead > 0) lastByteTime = lastRcvTime = microsecs();', 2)
    text = replace(text, 'void processMessage() {', 'void processMessage() {\n\texpirePartialHead();')
    text = replace(text, '\tlastRcvTime = microsecs();\n\tint firstByte', '\tint firstByte')
    text = replace(text, '(msgLength > MAX_MSG_SIZE)', '(msgLength < 1 || msgLength > MAX_MSG_SIZE)')
    text = replace(text, 'case chunkCode16Msg: // code chunk from 16-bit IDE',
                   'case chunkCode16Msg: // code chunk from 16-bit IDE\n\t\tif (bodyBytes < 3 || (bodyBytes & 1) == 0) break;')
    return text + '\nvoid smallvmResetTransport(void) {\n outBufStart=outBufEnd=0; rcvByteCount=0; lastByteTime=lastRcvTime=0;\n}\n'


def _data(text):
    # Native pointers into a compacting arena must not survive allocation.
    # newStringFromBytes snapshots its input before it allocates the result.
    before = '''\tOBJ result = newString(byteCount);
\tif (result) {
\t\tmemcpy(obj2str(result), start, byteCount);
\t}
\treturn result;'''
    text = replace(text, before, '\treturn newStringFromBytes(start, byteCount);')
    before = '''\t\tOBJ result = newString(byteCount);
\t\tif (result) {
\t\t\tmemcpy(obj2str(result), start, byteCount);
\t\t}
\t\treturn result;'''
    text = replace(text, before, '\t\treturn newStringFromBytes(start, byteCount);')
    text = replace(text, '\t\t\tmemcpy(&FIELD(result, 0), base + startIndex - 1, byteCount);',
                   '\t\t\tbase = (char *) &FIELD(args[0], 0); // refresh after possible GC\n'
                   '\t\t\tmemcpy(&FIELD(result, 0), base + startIndex - 1, byteCount);')
    text = replace(text, 'memcpy(&FIELD(result, 0), obj2str(arg), byteCount);',
                   'memcpy(&FIELD(result, 0), obj2str(args[0]), byteCount); // rooted argument may have moved')
    begin = text.index('OBJ primSplit(int argCount, OBJ *args) {')
    end = text.index('OBJ primJoinStrings(int argCount, OBJ *args) {', begin)
    text = text[:begin] + '''OBJ primSplit(int argCount, OBJ *args) {
\tif (argCount < 2) return fail(notEnoughArguments);
\tif (!IS_TYPE(args[0], StringType)) return fail(needsStringError);
\tif (!IS_TYPE(args[1], StringType)) return fail(needsStringError);
\tchar *source = obj2str(args[0]);
\tchar *delimiter = obj2str(args[1]);
\tint sourceBytes = strlen(source);
\tint delimiterBytes = strlen(delimiter);
\tint convertNums = (argCount > 2) && (args[2] == trueObj);
\tint resultCount = 0;
\tif (!delimiterBytes) {
\t\tresultCount = countUTF8(source);
\t} else {
\t\tresultCount = 1;
\t\tfor (char *match = strstr(source, delimiter); match;
\t\t\tmatch = strstr(match + delimiterBytes, delimiter)) resultCount++;
\t}
\t// Only integer byte offsets cross allocations; args and tempGCRoot are
\t// updated by GC. No cached native source/delimiter pointer survives it.
\ttempGCRoot = newObj(ListType, resultCount + 1, zeroObj);
\tif (!tempGCRoot) return falseObj;
\tFIELD(tempGCRoot, 0) = int2obj(resultCount);
\tif (resultCount == 1 && (delimiterBytes || convertNums)) {
\t\tFIELD(tempGCRoot, 1) = args[0]; // preserve the upstream unsplit case
\t\treturn tempGCRoot;
\t}
\tint offset = 0;
\tfor (int i = 0; i < resultCount; i++) {
\t\tsource = obj2str(args[0]);
\t\tdelimiter = obj2str(args[1]);
\t\tchar *last = source + offset;
\t\tchar *next = !delimiterBytes ? nextUTF8(last) :
\t\t\t((i + 1 == resultCount) ? source + sourceBytes : strstr(last, delimiter));
\t\tif (!next) return fail(unspecifiedError);
\t\tint nextOffset = next - source;
\t\tOBJ item = convertNums && substringIsInteger(last, next) ?
\t\t\tint2obj(substringToInteger(last, next)) : newStringFromBytes(last, nextOffset - offset);
\t\tif (!item) return falseObj;
\t\tFIELD(tempGCRoot, i + 1) = item;
\t\toffset = nextOffset + delimiterBytes;
\t}
\treturn tempGCRoot;
}

''' + text[end:]
    text = replace(text, '\tint fillWord = 0;', '\tuint32 fillWord = 0;')
    text = replace(text, 'fillWord = (fillByte << 24) | (fillByte << 16) | (fillByte << 8) | fillByte;',
                   'fillWord = ((uint32) fillByte << 24) | ((uint32) fillByte << 16) | ((uint32) fillByte << 8) | (uint32) fillByte;')
    before = '''\tint count;
\tif (end >= start) {
\t\tcount = ((end - start) / incr) + 1;
\t} else {
\t\tcount = ((start - end) / incr) + 1;
\t\tincr = -incr; // make the increment negative
\t}'''
    after = '''\tint64_t distance = end >= start ? (int64_t) end - start : (int64_t) start - end;
\tint64_t count64 = distance / incr + 1;
\tif (count64 > 65534) return fail(arraySizeError);
\tint count = (int) count64;
\tif (end < start) incr = -incr;'''
    return replace(text, before, after)


def patch_core(name, source):
    """Return the LP64 Linux variant of a canonical UTF-8 v417 VM source file."""
    name = name.removeprefix('vm/')
    if name not in SOURCE_SHA256:
        return source
    if hashlib.sha256(source.encode('utf-8')).hexdigest() != SOURCE_SHA256[name]:
        raise ValueError('Only canonical, unpatched v417 source is supported: ' + name)
    if name == 'interp.c':
        return _interpreter(source)
    if name == 'runtime.c':
        return _runtime(source)
    if name == 'dataPrims.c':
        return _data(source)
    if name == 'interp.h':
        source = replace(source, '#ifdef GNUBLOCKS', '#if defined(GNUBLOCKS) || defined(SMALLVM_LINUX_ARM64)')
        source = replace(source, 'void vmLoop(void);', 'void vmLoop(void);\nvoid vmSlice(unsigned cycles);\nvoid smallvmResetTransport(void);')
        source = replace(source, '\tSoundPrims,\n\tPrimitiveSetCount',
                         '\tSoundPrims,\n\tMicroDuckPrims,\n\tPrimitiveSetCount')
        source = replace(source, 'void primsInit();',
                         'void primsInit();\nvoid linuxMicroduckCancelPending(void);')
        before = '''static inline int evalInt(OBJ obj) {
\tif (isInt(obj)) {
\t\treturn obj2int(obj);
\t} else if (IS_TYPE(obj, StringType)) {
\t\t// try to parse an int out of a string
\t\treturn strtol(obj2str(obj), NULL, 10); // returns 0 if string is not a number
\t} else if (IS_TYPE(obj, ByteArrayType)) {
\t\t// try to parse an int out of a byte array (treating it as a string)
\t\treturn strtol((char *) &FIELD(obj, 0), NULL, 10); // returns 0 if string is not a number
\t} else {
\t\tfail(needsIntegerError);
\t\treturn 0;
\t}
}'''
        after = '''// Decimal-prefix conversion retains upstream whitespace/sign handling and
// returns zero for a non-number. Enforce the documented signed31 number range
// before narrowing; LP64 strtol otherwise admits INT32_MIN and can crash divide.
// Byte arrays have an exact byte length and need not have a null terminator.
// https://wiki.microblocks.fun/en/gp_syntax
static inline int smallvmParseInteger(const char *text, size_t bytes) {
\tsize_t at = 0;
\twhile (at < bytes && (text[at] == ' ' || (text[at] >= '\\t' && text[at] <= '\\r'))) at++;
\tint negative = at < bytes && text[at] == '-';
\tif (at < bytes && (text[at] == '-' || text[at] == '+')) at++;
\tuint32 limit = negative ? 1073741824u : 1073741823u;
\tuint32 value = 0;
\twhile (at < bytes && text[at] >= '0' && text[at] <= '9') {
\t\tuint32 digit = (uint32)(text[at++] - '0');
\t\tif (value > (limit - digit) / 10u) {
\t\t\tfail(cannotConvertToInteger);
\t\t\treturn 0;
\t\t}
\t\tvalue = value * 10u + digit;
\t}
\treturn negative ? -(int)value : (int)value;
}

static inline int evalInt(OBJ obj) {
\tif (isInt(obj)) return obj2int(obj);
\tif (IS_TYPE(obj, StringType)) return smallvmParseInteger(obj2str(obj), 4u * WORDS(obj));
\tif (IS_TYPE(obj, ByteArrayType)) return smallvmParseInteger((char *)&FIELD(obj, 0), BYTES(obj));
\tfail(needsIntegerError);
\treturn 0;
}'''
        return replace(source, before, after)
    if name == 'miscPrims.c':
        # long is 64 bits on Linux ARM64; preserve the VM's explicit signed31
        # bit interpretation, avoiding a signed left shift in hex/binary reads.
        source = replace(source, 'long result = strtol(s, NULL, 16);', 'int32_t result = (int32_t) strtol(s, NULL, 16);')
        source = replace(source, 'long result = strtol(s, NULL, 2);', 'int32_t result = (int32_t) strtol(s, NULL, 2);')
        return replace(source, 'result = (result << 1) >> 1;', 'result = (int32_t)((uint32) result << 1) >> 1;', 2)
    # varPrims operates through FIELD/obj2str, supplied by mem.h; its native
    # persistence-record pointers and compact references remain distinct.
    return source
