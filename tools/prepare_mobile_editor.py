#!/usr/bin/env python3
"""Prepare the reviewed offline mobile source cache. Never flash or deploy."""
# SPDX-License-Identifier: MIT
import argparse
import json
from pathlib import Path
from mobile_editor_source import prepare_archive

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--fetch', action='store_true')
    p.add_argument('--full-site', action='store_true', help='Reproduce the reviewed site for local inspection')
    a = p.parse_args()
    print(json.dumps(prepare_archive(a.archive, a.output, a.fetch, a.full_site), indent=2))
