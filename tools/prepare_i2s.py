#!/usr/bin/env python3
"""Prepare one audited ESP32 I2S guard without editing the pinned Zephyr tree."""
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import sys

source,output=map(Path,sys.argv[1:])
data=source.read_bytes()
expected='fe667681d819cbcf90fc695e99846455aa162cb88459396a51befa581a1f4d57'
if hashlib.sha256(data).hexdigest()!=expected:
    raise ValueError('Unexpected pinned Zephyr I2S source; review before applying guard')
text=data.decode('utf-8')
anchor='static int IRAM_ATTR i2s_esp32_tx_link(const struct device *dev, void *buffer, size_t size)\n{\n'
assert text.count(anchor)==1
text=text.replace(anchor,anchor+
    '\t/* A one-descriptor configuration cannot hold an appended chain.\n'
    '\t * Do not call dma_reload: an idle descriptor FSM can otherwise\n'
    '\t * replace the in-flight buffer instead of rejecting the append. */\n'
    '\tif (CONFIG_DMA_ESP32_MAX_DESCRIPTOR_NUM < 2) {\n'
    '\t\treturn -ENOSPC;\n'
    '\t}\n',1)
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(text,encoding='utf-8',newline='\n')
print('Prepared pinned ESP32 I2S single-descriptor append guard; upstream tree unchanged')
