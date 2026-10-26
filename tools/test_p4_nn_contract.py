#!/usr/bin/env python3
"""ASan/UBSan check of portable NN shape/product/dtype bounds."""
# SPDX-License-Identifier: MIT
import subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='p4-nn-contract-') as folder:
 output=Path(folder)/'nn-contract'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'common/nn'),str(root/'common/nn/nn_contract.c'),str(root/'tests/p4_nn_contract_test.c'),'-o',str(output)],check=True)
 subprocess.run([str(output)],check=True)
