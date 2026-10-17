#!/usr/bin/env python3
"""Prepare an audited v417 snapshot without modifying the upstream checkout."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Unexpected v417 source; patch anchor count is {text.count(old)}: {old[:70]!r}")
    return text.replace(old, new, 1)


def prepare(source, output):
    manifest = json.loads((source / "provenance.json").read_text())
    if manifest["canonical_commit"] != "2071df569623ba9cdcd6f8106b61796e047df38b":
        raise ValueError("Only the reviewed v417 source revision is supported")
    for item in manifest["files"]:
        path = Path(item["path"])
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "vm":
            raise ValueError("Unsafe source path")
        data = (source / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"Source hash mismatch: {path}")
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for name in ("LICENSE", "provenance.json"):
        (output / name).write_bytes((source / name).read_bytes())

    path = output / "vm/interp.c"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "\tif (errorCode) goto error; \\\n", "\tif (errorCode) goto error; \\\n\tif (!instructionBudget--) goto suspend; \\\n")
    text = replace_once(text, "static void runTask(Task *task) {", "static void runTask(Task *task) {\n\tunsigned instructionBudget = 256;")
    text = replace_once(text, "void vmLoop() {", "void vmSlice(unsigned cycles) {")
    text = replace_once(text, "\tint currentTaskIndex = 0;\n\tint count = 0;\n\twhile (true) {", "\tstatic int currentTaskIndex = 0;\n\tstatic int count = 0;\n\twhile (cycles--) {")
    text = replace_once(text, "#endif // not __EMSCRIPTEN__", "void vmLoop() { while (true) vmSlice(1); }\n\n#endif // not __EMSCRIPTEN__")
    path.write_text(text, encoding="utf-8", newline="\n")
    path = output / "vm/interp.h"
    text = replace_once(path.read_text(encoding="utf-8"), "void vmLoop(void);", "void vmLoop(void);\nvoid vmSlice(unsigned cycles);")
    path.write_text(text, encoding="utf-8", newline="\n")

    path = output / "vm/runtime.c"
    text = replace_once(path.read_text(encoding="utf-8"), "#ifdef __ZEPHYR__", "#if defined(__ZEPHYR__) && !defined(SMALLVM_ZEPHYR)")
    text = text.replace("delay(", "smallvmDelay(")
    text = replace_once(text, "uint32 lastRcvTime = 0;", "uint32 lastRcvTime = 0;\nstatic uint32 lastByteTime = 0;")
    text = replace_once(text,
        "\tuint32 usecs = microsecs();\n\tif (usecs < lastRcvTime) lastRcvTime = 0; // clock wrap\n\treturn (usecs - lastRcvTime) > 20000;",
        "\treturn (uint32)(microsecs() - lastByteTime) > 250000;")
    text = replace_once(text,
        "void captureIncomingBytes() {",
        "static void expirePartialHead(void) {\n"
        "\tif (!rcvByteCount || !receiveTimeout()) return;\n"
        "\tint partial = (rcvBuf[0] == 250 && rcvByteCount < 3);\n"
        "\tif (rcvBuf[0] == 251) partial = rcvByteCount < 5 ||\n"
        "\t\t(rcvByteCount < 5 + ((rcvBuf[4] << 8) | rcvBuf[3]));\n"
        "\tif (partial) rcvByteCount = 0;\n}\n\n"
        "void captureIncomingBytes() {\n\texpirePartialHead();")
    text = text.replace(
        "int bytesRead = recvBytes(&rcvBuf[rcvByteCount], RCVBUF_SIZE - rcvByteCount);",
        "int bytesRead = recvBytes(&rcvBuf[rcvByteCount], RCVBUF_SIZE - rcvByteCount);\n"
        "\tif (bytesRead > 0) lastByteTime = lastRcvTime = microsecs();")
    text = replace_once(text, "void processMessage() {", "void processMessage() {\n\texpirePartialHead();")
    text = replace_once(text, "\tlastRcvTime = microsecs();\n\tint firstByte", "\tint firstByte")
    text = replace_once(text, "(msgLength > MAX_MSG_SIZE)", "(msgLength < 1 || msgLength > MAX_MSG_SIZE)")
    text = replace_once(text, "case chunkCode16Msg: // code chunk from 16-bit IDE", "case chunkCode16Msg: // code chunk from 16-bit IDE\n\t\tif (bodyBytes < 3 || (bodyBytes & 1) == 0) break;")
    text += "\nvoid smallvmResetTransport(void) {\n outBufStart=outBufEnd=0; rcvByteCount=0; lastByteTime=lastRcvTime=0;\n}\n"
    path.write_text(text, encoding="utf-8", newline="\n")

    path = output / "vm/persist.c"
    text = replace_once(path.read_text(encoding="utf-8"), "#elif defined(__ZEPHYR__)", "#elif defined(__ZEPHYR__) && !defined(SMALLVM_ZEPHYR)")
    text = replace_once(text, "\t#if defined(ESP8266)\n\t\t#define USE_CODE_FILE", "\t#if defined(SMALLVM_ZEPHYR)\n\t\t#define HALF_SPACE (64 * 1024)\n\t#elif defined(ESP8266)\n\t\t#define USE_CODE_FILE")
    text = replace_once(text, "static uint8 flash[HALF_SPACE] __attribute__ ((aligned (32)));",
        "#if defined(SMALLVM_ZEPHYR) && defined(CONFIG_ESP_SPIRAM)\n"
        "\tstatic uint8 flash[HALF_SPACE] __attribute__((aligned(32), section(\".ext_ram.bss\")));\n"
        "\t#else\n\tstatic uint8 flash[HALF_SPACE] __attribute__((aligned(32)));\n\t#endif")
    text = text.replace("Compacted RAM code store (%lu msecs)", "Compacted RAM code store (%u msecs)")
    text += "\n#ifdef SMALLVM_ZEPHYR\nunsigned char *smallvmCodeData(void) { return flash; }\nunsigned smallvmCodeSize(void) { return sizeof(flash); }\n#endif\n"
    path.write_text(text, encoding="utf-8", newline="\n")

    path = output / "vm/mem.c"
    text = replace_once(path.read_text(encoding="utf-8"), "#if defined(NRF51)", "#if defined(SMALLVM_ZEPHYR)\n\t#define OBJSTORE_BYTES (64 * 1024)\n#elif defined(NRF51)")
    text = replace_once(text, "static OBJ objstore[OBJSTORE_WORDS];",
        "#if defined(SMALLVM_ZEPHYR) && defined(CONFIG_ESP_SPIRAM)\n"
        "\tstatic OBJ objstore[OBJSTORE_WORDS] __attribute__((section(\".ext_ram.bss\")));\n"
        "\t#else\n\tstatic OBJ objstore[OBJSTORE_WORDS];\n\t#endif")
    path.write_text(text, encoding="utf-8", newline="\n")
    path = output / "vm/mem.h"
    text = replace_once(path.read_text(encoding="utf-8"),
        "#define int2obj(n) ((OBJ) (((n) << 1) | 1))",
        "#define int2obj(n) ((OBJ) (((uint32) (n) << 1) | 1u))")
    path.write_text(text, encoding="utf-8", newline="\n")
    print("Prepared verified SmallVM v417 with bounded scheduling and RAM-only code storage")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.source.resolve(), args.output.resolve())
