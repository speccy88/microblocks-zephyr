"""Deliberate host-test operations; never a simulated physical device."""
# SPDX-License-Identifier: MIT
import os
import time
from ..api import arguments


class Extension:
    def __init__(self,settings,context):
        self.state=context.state
        self.operations={'delay':self.delay,'echo':lambda args:args,'crash':self.crash,'oversized_write':self.oversized_write}

    def delay(self,args):
        arguments(args,{'seconds','value'})
        time.sleep(min(float(args.get('seconds',.1)),30))
        return args.get('value',42)

    def crash(self,args):os._exit(7)

    def oversized_write(self,args):
        with (self.state/'fixture-write.txt').open('a') as stream:stream.write('one write\n')
        return 'x'*60001
