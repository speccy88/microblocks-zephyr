#!/usr/bin/env python3
"""Native host RoboEyes/OLED/pose tests with ASan/UBSan; no device access."""
# SPDX-License-Identifier: MIT
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='robot-eyes-') as tmp:
        work=Path(tmp);objects=[]
        includes=['-I'+str(root/'common/eyes'),'-I'+str(root/'common/pose')]
        flags=['-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror']
        for source in ['common/eyes/oled.c','common/pose/pose.c','common/pose/camera_wire.c','common/pose/face.c','common/pose/serial_rate.c']:
            obj=work/(Path(source).stem+'.o');objects.append(str(obj))
            subprocess.run(['cc','-std=c11',*flags,*includes,'-c',str(root/source),'-o',str(obj)],check=True)
        binary=work/'test'
        subprocess.run(['c++','-std=c++17',*flags,*includes,'-isystem',str(root/'build-artifacts/roboeyes/src'),
                        str(root/'common/eyes/roboeyes.cpp'),str(root/'tests/eyes_pose_test.cpp'),*objects,'-o',str(binary)],check=True)
        result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
        report=json.loads(result.stdout);report['sanitizers']='address,undefined'
        print(json.dumps(report,indent=2))
        if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n')
