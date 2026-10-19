#!/usr/bin/env python3
"""Verify real IDE assets and generate compressed flash-backed HTTP resources."""
# SPDX-License-Identifier: MIT
import argparse
import gzip
import hashlib
import json
import mimetypes
import re
from pathlib import Path
from package_pages import xrp_package


def package(source, output, project):
    manifest = json.loads((project / "dependencies/ide-assets.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    resources = []
    audit = []
    assembly = ['.section .rodata.web_assets,"a",%progbits']
    replacements = {
        "unoq-network.js": project / "web/xrp-network.js",
    }
    originals = {}
    for name in ("gp_wasm.js", "gp_wasm.data"):
        entry = next(x for x in manifest["files"] if x["path"] == name)
        originals[name] = (source / name).read_bytes()
        if hashlib.sha256(originals[name]).hexdigest() != entry["sha256"]:
            raise ValueError(f"IDE source hash mismatch: {name}")
    patched_js, patched_data = xrp_package(originals["gp_wasm.js"], originals["gp_wasm.data"])
    # The engine may become ready before deferred head scripts have executed.
    # Run it after parsing and hold main() until the local English catalog is ready.
    locale_gate = b'''Module.preRun.push(function() {
 addRunDependency('board-english');
 Promise.resolve(GetText.ready).then(function() { removeRunDependency('board-english'); },
  function() { Module.setStatus('Cannot load local language assets. Reload to retry.'); });
});
'''
    patched = {"gp_wasm.js": locale_gate + patched_js, "gp_wasm.data": patched_data}
    files = list(manifest["files"])
    for index, item in enumerate(files):
        name = item["path"]
        data = (item["local"] if "local" in item else source / name).read_bytes()
        if "sha256" in item and hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"IDE source hash mismatch: {name}")
        if name in replacements:
            data = replacements[name].read_bytes()
        if name in patched:
            data = patched[name]
        if name == "microblocks.html":
            data, count = re.subn(rb'(<script[^>]+src="gp_wasm\.js[^\"]*")', rb'\1 defer', data)
            if count != 1:
                raise ValueError("Expected one GP engine bootstrap script")
            hook = b"document.addEventListener('ready', () => { IDE.init(); });"
            if data.count(hook) != 1:
                raise ValueError("Expected one IDE initialization hook")
            data = data.replace(hook, b"document.addEventListener('ready', () => { IDE.init(); document.dispatchEvent(new Event('board-ide-ready')); });")
        if name == "gettext.js":
            for old, new in (
                (b"GetText.readLocale('en');", b"GetText.ready = GetText.readLocale('en');"),
                (b"\tfetch('translations/' + langcode + '.po')", b"\treturn fetch('translations/' + langcode + '.po')"),
                (b"GetText.setLocale = function (langcode) {", b"GetText.setLocale = function (langcode) {\n\tif (!langcode) { langcode = 'en'; }"),
            ):
                if data.count(old) != 1:
                    raise ValueError("Unexpected pinned language bootstrap source")
                data = data.replace(old, new)
        compressed = gzip.compress(data, compresslevel=9, mtime=0)
        encoding = "gzip" if len(compressed) < len(data) else ""
        blob = compressed if encoding else data
        path = output / f"asset-{index}.bin"
        path.write_bytes(blob)
        label = f"mb_asset_{index}"
        assembly += [f".global {label}", f"{label}:", f'.incbin "{path.as_posix()}"']
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if name == "setup":
            content_type = "text/html"
        if name.endswith(".wasm"):
            content_type = "application/wasm"
        resources.append((name, label, len(blob), encoding, content_type))
        audit.append({"path":"/"+name,"encoding":encoding,"content_type":content_type,
            "bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
            "flash_bytes":len(blob),"flash_sha256":hashlib.sha256(blob).hexdigest()})
    (output / "assets.S").write_text("\n".join(assembly) + "\n")
    code = ['#include "server.h"', '#include <zephyr/net/http/service.h>']
    for index, (name, label, size, encoding, mime) in enumerate(resources):
        code += [f"extern const unsigned char {label}[];",
                 f'static const struct mb_asset asset_{index} = {{{label}, {size}, {"true" if encoding else "false"}}};',
                 f"static struct http_resource_detail_dynamic detail_{index} = {{",
                 " .common = {.type=HTTP_RESOURCE_TYPE_DYNAMIC, .bitmask_of_supported_http_methods=BIT(HTTP_GET),",
                 f' .content_type={json.dumps(mime)}, .content_encoding={json.dumps(encoding) if encoding else "NULL"}}},',
                 f" .cb=mb_asset_handler, .user_data=(void *)&asset_{index}}};",
                 f'HTTP_RESOURCE_DEFINE(resource_{index}, mb_http, {json.dumps("/" + name)}, &detail_{index});']
        if name == "microblocks.html":
            code.append(f'HTTP_RESOURCE_DEFINE(asset_root, mb_http, "/", &detail_{index});')
    (output / "assets.c").write_text("\n".join(code) + "\n")
    total = sum(x[2] for x in resources)
    (output / "assets-report.json").write_text(json.dumps({"files": len(resources), "flash_bytes": total,"assets":audit}, indent=2))
    print(f"Packaged {len(resources)} real IDE files into {total} flash bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    package(args.source.resolve(), args.output.resolve(), Path(__file__).resolve().parents[1])
