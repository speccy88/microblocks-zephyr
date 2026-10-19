#!/usr/bin/env python3
"""Compare every public Pages asset with an already verified local build.

Read-only HTTP requests; no credentials, browser/device control or uploads.
"""
# SPDX-License-Identifier: MIT
import argparse
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request


def audit(build, site, commit):
    parsed = urllib.parse.urlsplit(site)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTPS site root without credentials, query or fragment')
    if not (build / '.portal-build').is_file():
        raise ValueError('Expected an owned, verified portal build')
    paths = sorted(p for p in build.rglob('*') if p.is_file()
                   and p.name not in ('.portal-build', '.nojekyll'))

    def check(path):
        name = path.relative_to(build).as_posix()
        local = path.read_bytes()
        expected = hashlib.sha256(local).hexdigest()
        result = {'path': name, 'expected_sha256': expected}
        try:
            request = urllib.request.Request(site.rstrip('/') + '/' + urllib.parse.quote(name),
                                             headers={'User-Agent': 'MicroBlocks-Pages-acceptance'})
            with urllib.request.urlopen(request, timeout=20) as response:
                remote = response.read(len(local) + 1)
                result.update(http_status=response.status, bytes=len(remote),
                              sha256=hashlib.sha256(remote).hexdigest())
            result['result'] = 'PASS' if result['http_status'] == 200 and remote == local else 'FAIL'
        except Exception as error:
            result.update(result='FAIL', error_type=type(error).__name__)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        assets = list(pool.map(check, paths))
    return {'tested_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'url': site, 'source_commit': commit, 'files': len(assets),
            'bytes': sum(x.get('bytes', 0) for x in assets),
            'result': 'PASS' if all(x['result'] == 'PASS' for x in assets) else 'FAIL',
            'assets': assets}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--site', required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.build, args.site, args.source_commit)
    args.evidence.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'assets'}, indent=2))
    print('Failures:', json.dumps([x for x in report['assets'] if x['result'] != 'PASS']))
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
