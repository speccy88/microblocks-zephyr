#!/usr/bin/env python3
"""Inspect an XRP build's real ELF/UF2, linked APIs, config and source identity.

Run with the existing Zephyr Python (pyelftools), SDK nm and Ninja. No device
or network access. A PASS is a cross-build result, never a physical result.
"""
# SPDX-License-Identifier: MIT
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
from elftools.elf.elffile import ELFFile

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(args):
    repo=Path(__file__).resolve().parents[1];build=args.build.resolve();z=build/'zephyr'
    files=subprocess.check_output(['git','-C',str(repo),'ls-files'],text=True).splitlines()
    selected=[p for p in files if (p.startswith(('boards/sparkfun_xrp_rp2350/','common/')) and
        (Path(p).suffix in ('.c','.cpp','.h','.dts','.dtsi','.conf','.yml','.yaml','.cmake','.ld') or
         Path(p).name.startswith('Kconfig') or Path(p).name=='CMakeLists.txt')) or p in (
        'tools/prepare_smallvm.py','tools/prepare_xrp_runtime.py','tools/prepare_xrp_arduino.py',
        'tools/package_xrp_ide.py','tools/package_pages.py','web/xrp-network.js')]
    hashes={}
    for relative in selected:
        data=(repo/relative).read_bytes()
        original=subprocess.check_output(['git','-C',str(repo),'show',args.source_commit+':'+relative])
        if data!=original: raise ValueError('Source changed after recorded commit: '+relative)
        hashes[relative]=hashlib.sha256(data).hexdigest()
    with (z/'zephyr.elf').open('rb') as stream:
        elf=ELFFile(stream)
        assert elf.elfclass==32 and elf.little_endian and elf['e_machine']=='EM_ARM'
        segments=[]
        for p in elf.iter_segments():
            if p['p_type']!='PT_LOAD':continue
            if p['p_filesz']:
                assert 0x10000000<=p['p_paddr'] and p['p_paddr']+p['p_filesz']<=0x10800000
            segments.append(dict(physical=hex(p['p_paddr']),virtual=hex(p['p_vaddr']),file_bytes=p['p_filesz'],memory_bytes=p['p_memsz']))
        symbols={s.name for s in elf.get_section_by_name('.symtab').iter_symbols()}
    required=['vmSlice','restoreScripts','xrp_transport_poll','xrp_provision_message','mbnw_flash_store_open',
              'mbnw_store_save','mb_store_load','mb_store_poll','addEncoderPrims','xrp_capture_start','whd_wifi_join']
    assert all(s in symbols for s in required),set(required)-symbols
    demangled=subprocess.check_output([args.nm,'-C','--defined-only',str(z/'zephyr.elf')],text=True)
    for api in (' analogRead(', ' pinMode(', 'arduino::ZephyrI2C::begin()'):
        assert api in demangled,api
    uf2=(z/'zephyr.uf2').read_bytes();assert len(uf2)%512==0
    blocks=len(uf2)//512
    for i in range(blocks):
        block=uf2[i*512:(i+1)*512]
        a,b,flags,address,size,index,total,family=struct.unpack_from('<8I',block)
        assert (a,b,struct.unpack_from('<I',block,508)[0])==(0x0a324655,0x9e5d5157,0x0ab16f30)
        assert flags&0x2000 and not flags&1 and family==0xe48bff59 and index==i and total==blocks
        assert 0<size<=476 and 0x10000000<=address and address+size<=0x10800000
    config=dict(line.split('=',1) for line in (z/'.config').read_text().splitlines() if line.startswith('CONFIG_') and '=' in line)
    enabled=('CONFIG_SOC_RP2350B','CONFIG_WIFI_AIROC','CONFIG_CYW43439','CONFIG_ARDUINO_API','CONFIG_ENTROPY_RPI_PICO_RNG')
    disabled=('CONFIG_CONSOLE','CONFIG_PRINTK','CONFIG_LOG','CONFIG_BT','CONFIG_TIMER_RANDOM_GENERATOR','CONFIG_TEST_CSPRNG_GENERATOR')
    assert all(config.get(k)=='y' for k in enabled),{k:config.get(k) for k in enabled}
    assert all(config.get(k)!='y' for k in disabled)
    commands=subprocess.check_output([args.ninja,'-C',str(build),'-t','commands'],text=True)
    line=next(l for l in commands.splitlines() if '/variants/sparkfun_xrp/pinmux.c' in l and ' -c ' in l)
    tokens=shlex.split(line);clean=[];i=0
    while i<len(tokens):
        if tokens[i] in ('-o','-MF','-MT'):i+=2;continue
        if tokens[i] in ('-c','-MD'):i+=1;continue
        clean.append(tokens[i]);i+=1
    macros=subprocess.check_output(clean+['-E','-dM'],cwd=build,text=True)
    macro_values={}
    for name in ('PICO_RP2350A','NUM_BANK0_GPIOS','NUM_ADC_CHANNELS'):
        m=re.search(r'^#define '+name+r' (.+)$',macros,re.M);macro_values[name]=m[1] if m else None
    assert macro_values['PICO_RP2350A'] in (None,'0')
    assert macro_values['NUM_BANK0_GPIOS'] in ('48','48u','_u(48)')
    assert macro_values['NUM_ADC_CHANNELS'] in ('9','9u','_u(9)')
    log=args.log.read_text()
    flash=int(re.findall(r'FLASH:\s+(\d+) B',log)[-1]);ram=int(re.findall(r'RAM:\s+(\d+) B',log)[-1])
    return dict(result='PASS, cross-build and artifact inspection only',tested_at=datetime.now(timezone.utc).isoformat(),
        source_commit=args.source_commit,target='sparkfun_xrp/rp2350b/m33_0',zephyr_commit='a915b2f12675b48b16d56653ea145dcd8f20cbbf',
        build_directory=str(build),flash_used_bytes=flash,ram_linker_used_bytes=ram,
        segments=segments,required_linked_symbols=required,arduino_api_symbols_verified=True,actual_compiler_macros=macro_values,
        config={k:config.get(k,'n') for k in enabled+disabled+('CONFIG_WHD_WIFI_COUNTRY',)},
        artifacts={n:dict(bytes=(z/n).stat().st_size,sha256=digest(z/n)) for n in ('zephyr.elf','zephyr.uf2','zephyr.bin')},
        source_sha256=hashes,assets=json.loads((build/'web-xrp/assets-report.json').read_text()),
        uf2_family='0xe48bff59 ARM Secure',program_and_settings_not_loaded=True,
        flashed=False,physical_tested=False,actuators_enabled=False,credentials_used=False,psram_mapped=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',required=True,type=Path);p.add_argument('--source-commit',required=True)
    p.add_argument('--nm',required=True);p.add_argument('--ninja',required=True)
    p.add_argument('--log',required=True,type=Path);p.add_argument('--evidence',required=True,type=Path)
    args=p.parse_args();report=verify(args)
    args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:report[k] for k in ('result','source_commit','flash_used_bytes','ram_linker_used_bytes','actual_compiler_macros','artifacts')},indent=2))
