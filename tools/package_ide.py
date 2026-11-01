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
import mobile_board_assets as mobile
from patch_ide import patch_ide


def package(source, output, project, mobile_source=None):
    extra = mobile.assets(mobile.source_for(source, mobile_source), 'waveshare')
    manifest = json.loads((project / "dependencies/ide-assets.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    resources = []
    audit = []
    assembly = ['.section .rodata.web_assets,"a",@progbits']
    replacements = {
        "unoq-network.js": project / "web/board-network.js",
    }
    originals = {}
    for name in ("gp_wasm.js", "gp_wasm.data"):
        entry = next(x for x in manifest["files"] if x["path"] == name)
        originals[name] = (source / name).read_bytes()
        if hashlib.sha256(originals[name]).hexdigest() != entry["sha256"]:
            raise ValueError(f"IDE source hash mismatch: {name}")
    patched_js, patched_data = patch_ide(originals["gp_wasm.js"], originals["gp_wasm.data"],
        (project / "boards/waveshare_esp32s3_rlcd_4_2/integration/Waveshare_RLCD_4_2.ubl").read_bytes())
    # The engine may become ready before deferred head scripts have executed.
    # Run it after parsing and hold main() until the local English catalog is ready.
    locale_gate = b'''Module.preRun.push(function() {
 addRunDependency('board-english');
 Promise.resolve(GetText.ready).then(function() { removeRunDependency('board-english'); },
  function() { Module.setStatus('Cannot load local language assets. Reload to retry.'); });
});
'''
    patched = {"gp_wasm.js": locale_gate + patched_js, "gp_wasm.data": patched_data}
    files = list(manifest["files"]) + [{"path": "setup", "local": project / "web/setup.html"}]
    files += [{"path": name, "mobile": raw} for name, raw in sorted(extra.items())]
    for index, item in enumerate(files):
        name = item["path"]
        data = item["mobile"] if "mobile" in item else (item["local"] if "local" in item else source / name).read_bytes()
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
        if extra and name == "microblocks.html":
            data = mobile.desktop(data)
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
                 f'HTTP_RESOURCE_DEFINE(resource_{index}, mb_http, {json.dumps(mobile.route(name) if extra else "/" + name)}, &detail_{index});']
        if name == ("index.html" if extra else "microblocks.html"):
            code.append(f'HTTP_RESOURCE_DEFINE(asset_root, mb_http, "/", &detail_{index});')
        if name == "mobile/index.html":
            code += [f'HTTP_RESOURCE_DEFINE(asset_mobile, mb_http, "/mobile", &detail_{index});',
                     f'HTTP_RESOURCE_DEFINE(asset_mobile_dir, mb_http, "/mobile/", &detail_{index});']
    (output / "assets.c").write_text("\n".join(code) + "\n")
    total = sum(x[2] for x in resources)
    (output / "assets-report.json").write_text(json.dumps({"files": len(resources), "flash_bytes": total,"assets":audit,"mobile":mobile.summary(extra)}, indent=2))
    print(f"Packaged {len(resources)} real IDE files into {total} flash bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mobile-source", type=Path)
    args = parser.parse_args()
    package(args.source.resolve(), args.output.resolve(), Path(__file__).resolve().parents[1], args.mobile_source)
