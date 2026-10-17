#!/usr/bin/env python3
"""Apply the reviewed Wire fixes to the pinned upstream API checkout."""
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import subprocess
import urllib.request
from pathlib import Path
import yaml

REVISION = 'af5b8610f9be6d7b962e2ba6dd8e6859697c44ff'
parser = argparse.ArgumentParser()
parser.add_argument('module', type=Path)
parser.add_argument('--fetch-api',action='store_true',help='Download missing verified API source blobs')
args = parser.parse_args()
root = args.module.resolve()
revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
if revision != REVISION:
    raise SystemExit('Arduino API checkout must match the pinned revision')
metadata=yaml.safe_load(subprocess.check_output(['git','-C',str(root),'show','HEAD:zephyr/module.yml']))
for blob in metadata.get('blobs',[]):
    relative_path=Path(blob['path'])
    if relative_path.is_absolute() or '..' in relative_path.parts:raise SystemExit('Unsafe API blob path')
    path=root/'zephyr/blobs'/relative_path
    if not path.exists() and args.fetch_api:
        if not blob['url'].startswith('https://'):raise SystemExit('API source URL must use HTTPS')
        data=urllib.request.urlopen(blob['url'],timeout=30).read()
        if hashlib.sha256(data).hexdigest()!=blob['sha256']:raise SystemExit('API source hash mismatch')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=blob['sha256']:
        raise SystemExit('Missing or changed API source blob: '+str(relative_path)+'; use --fetch-api')
relative = 'libraries/Wire/Wire.cpp'
pristine = subprocess.check_output(['git', '-C', str(root), 'show', 'HEAD:' + relative]).decode('utf-8')
patched = pristine.replace('\ti2c_dev->ops.init(i2c_dev);',
    '\t// Zephyr already initialized this device. Reinitializing allocates a second IRQ.\n'
    '\tif (!device_is_ready(i2c_dev)) LOG_ERR("I2C device is not ready");')
patched = patched.replace('return !ring_buf_is_empty(&rxRingBuffer.rb);',
    'return ring_buf_size_get(&rxRingBuffer.rb);')
patched = patched.replace('void arduino::ZephyrI2C::setClock(uint32_t freq) {\n}',
    'void arduino::ZephyrI2C::setClock(uint32_t freq) {\n'
    '\tuint32_t speed;\n'
    '\tif (freq == 100000) speed = I2C_SPEED_STANDARD;\n'
    '\telse if (freq == 400000) speed = I2C_SPEED_FAST;\n'
    '\telse if (freq == 1000000) speed = I2C_SPEED_FAST_PLUS;\n'
    '\telse { LOG_ERR("Unsupported I2C clock"); return; }\n'
    '\tif (i2c_configure(i2c_dev, I2C_MODE_CONTROLLER | I2C_SPEED_SET(speed)))\n'
    '\t\tLOG_ERR("I2C clock configuration failed");\n}')
if patched == pristine or 'i2c_dev->ops.init(i2c_dev)' in patched:
    raise SystemExit('Unexpected upstream Wire patch anchors')
target = root / relative
current = target.read_text(encoding='utf-8')
if current not in (pristine, patched):
    raise SystemExit('Wire.cpp has unrelated modifications; refusing to overwrite')
if current != patched:
    target.write_text(patched, encoding='utf-8', newline='\n')
print('Pinned Arduino Wire fixes verified: device initialization, byte count, setClock')
