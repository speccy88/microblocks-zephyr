#!/usr/bin/env python3
"""Write a review candidate; never fetch, move branches, or replace the pin."""
# SPDX-License-Identifier: MIT
import argparse
import json
from pathlib import Path
from js_editor_source import candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--candidate', required=True, type=Path)
    args = parser.parse_args()
    manifest = candidate(args.source, args.commit)
    with args.candidate.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(manifest, ensure_ascii=True, indent=2) + '\n')
    print(f"Candidate: {manifest['source_commit']} ({len(manifest['files'])} files)")


if __name__ == '__main__':
    main()
