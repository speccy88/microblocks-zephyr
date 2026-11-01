#!/usr/bin/env python3
"""Optional, offline touch assets for the three existing board HTTP servers."""
# SPDX-License-Identifier: MIT
import gzip
import hashlib
from pathlib import Path
from urllib.parse import quote
from add_mobile_web import entry_tags
from package_mobile_editor import ROOT, mobile_files


def source_for(ide, explicit=None):
    source = Path(explicit) if explicit else Path(ide) / 'mobile-editor'
    if explicit and not source.is_dir():
        raise ValueError('Explicit mobile source cache does not exist: ' + str(source))
    return source if source.is_dir() else None


def assets(source, board):
    if source is None:
        return {}
    mobile, _ = mobile_files(source, runtime='board', board=board,
                             desktop='../microblocks.html?layout=desktop')
    result = {'mobile/' + path: raw for path, raw in mobile.items()}
    # Root only chooses a layout. Neither editor runs before the choice.
    tags = entry_tags({'surface': 'chooser', 'mobile': 'mobile/index.html',
                       'desktop': 'microblocks.html?layout=desktop'})
    result['index.html'] = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        '<title>MicroBlocks on your board</title>' + tags + '</head><body><main>'
        '<noscript>JavaScript is required. <a href="microblocks.html">Desktop editor</a></noscript>'
        '</main></body></html>').encode()
    for name in ['mobile-entry.js', 'mobile-entry.css']:
        result[name] = (ROOT / 'web/mobile' / name).read_bytes()
    return result


def desktop(raw):
    if raw.count(b'</head>') != 1:
        raise ValueError('Review changed board desktop document')
    return raw.replace(b'</head>', entry_tags({'surface': 'desktop',
        'mobile': 'mobile/index.html', 'desktop': 'microblocks.html?layout=desktop'}).encode() + b'</head>')


def route(name):
    # HTTP parsers intentionally keep encoded paths; never broaden their input.
    # Match fetch(URL).pathname: URL path punctuation stays literal, while
    # spaces, Unicode, query/fragment delimiters and quotes are encoded.
    return '/' + quote(name, safe="/-._~!$&'()*+,;=:@")


def summary(extra):
    flash = sum(min(len(raw), len(gzip.compress(raw, compresslevel=9, mtime=0))) for raw in extra.values())
    return {'enabled': bool(extra), 'added_files': len(extra), 'added_flash_bytes': flash,
            'physical_hardware_validated': False, 'firmware_compiled': False,
            'note': 'Final linker RAM/flash and physical HTTP acceptance are required before installation.'}
