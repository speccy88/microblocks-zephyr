"""Execute the real aggregate gate so splitting WebKit cannot weaken CI."""
# SPDX-License-Identifier: MIT
from contextlib import redirect_stdout
import io
import itertools
import os
from pathlib import Path
import textwrap
import unittest
from unittest.mock import patch

WORKFLOW=Path(__file__).resolve().parents[1]/'.github/workflows/mobile-web.yml'

def guard():
    source=WORKFLOW.read_text(encoding='utf-8')
    block=source.split('# BEGIN_CHECKED_MOBILE_JOBS\n',1)[1].split('# END_CHECKED_MOBILE_JOBS',1)[0]
    return compile(textwrap.dedent(block),str(WORKFLOW),'exec')

class MobileCIGate(unittest.TestCase):
    def test_only_two_completed_successes_pass_the_actual_guard(self):
        statuses=('success','failure','cancelled','skipped','','timed_out','neutral','unknown')
        for chrome,webkit in itertools.product(statuses,repeat=2):
            with self.subTest(chrome=chrome,webkit=webkit),patch.dict(os.environ,{'CHROME_VM_RESULT':chrome,'WEBKIT_RESULT':webkit},clear=True),redirect_stdout(io.StringIO()):
                if chrome==webkit=='success':exec(guard(),{})
                else:
                    with self.assertRaises(SystemExit):exec(guard(),{})

    def test_missing_job_results_fail_closed(self):
        for values in ({},{'CHROME_VM_RESULT':'success'},{'WEBKIT_RESULT':'success'}):
            with self.subTest(values=values),patch.dict(os.environ,values,clear=True):
                with self.assertRaises(KeyError):exec(guard(),{})

if __name__=='__main__':unittest.main()
