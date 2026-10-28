"""Link/run the real worker with optional Zephyr diagnostic symbols absent."""
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform=='linux' and shutil.which('cc'),'Linux C sanitizer compiler required')
class OptionalStackDiagnostics(unittest.TestCase):
    def test_worker_links_and_releases_with_all_diagnostic_configurations(self):
        result=subprocess.run([sys.executable,str(ROOT/'tools/test_p4_sd_backend.py')],capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual({v['configuration'] for v in report['variants']},{'enabled','disabled','init_only','info_only'})
        for variant in report['variants']:
            self.assertEqual(variant['worker_runs'],25)
            self.assertEqual(variant['job_allocations'],variant['job_frees'])
            self.assertEqual(variant['stack_allocations'],variant['stack_frees'])
        files=subprocess.run([sys.executable,str(ROOT/'tools/test_p4_sd_file_worker.py')],capture_output=True,text=True,timeout=45)
        self.assertEqual(files.returncode,0,files.stdout+files.stderr)
        file_report=json.loads((ROOT/'build-artifacts/p4-sd-worker-tests/files-report.json').read_text())
        self.assertEqual(file_report['file_worker_runs'],4)
        self.assertEqual(file_report['job_allocations'],file_report['job_frees'])
        self.assertEqual(file_report['stack_allocations'],file_report['stack_frees'])
