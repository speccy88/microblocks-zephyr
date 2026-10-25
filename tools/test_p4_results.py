#!/usr/bin/env python3
"""Compile actual portable result store with ASan/UBSan; no hardware/network."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import subprocess,tempfile,os
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='p4-results-') as folder:
 binary=Path(folder)/'results-test'
 command=['cc','-std=c11','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-DMEDIA_ALLOC_EXTERNAL=1']
 for name in ['image','audio','media']:command+=['-I'+str(root/'common'/name)]
 command += [str(root/'tests/p4_results_test.c'),str(root/'common/image/image_store.c'),str(root/'common/audio/audio_store.c'),str(root/'common/media/result_store.c'),'-o',str(binary)]
 subprocess.run(command,check=True)
 subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1'})
