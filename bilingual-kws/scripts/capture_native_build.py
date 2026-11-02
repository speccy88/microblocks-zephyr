"""Build and inspect native artifacts offline; never opens a device or flashes.

Run using the west workspace Python (pyelftools is a Zephyr dependency).
The report records actual linked model bytes, rather than source declarations.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from common import PROJECT, save, digest

REPO = PROJECT.parent

def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()

def run(a):
    previous_path=PROJECT/'reports/native-build.json'
    previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
    model = PROJECT / 'models/voice_commands_int8.tflite'
    expected = digest(model)
    env = dict(os.environ, P4_WORKSPACE=str(a.workspace), P4_VOICE_MODEL=str(model))
    if a.whistle_model:
        if not a.whistle_sources:
            raise ValueError('--whistle-sources is required with --whistle-model')
        env.update(P4_WHISTLE_MODEL=str(a.whistle_model), P4_WHISTLE_SOURCES=str(a.whistle_sources))
    else:
        env.pop('P4_WHISTLE_MODEL', None)
        env.pop('P4_WHISTLE_SOURCES', None)
    command = ['bash', str(PROJECT / 'esp32p4/build.sh')]
    reports = PROJECT / 'reports'
    started = time.time()
    with (reports / 'native-build.txt').open('w') as log:
        log.write('BUILD ONLY — no serial, flash or reset operations\n')
        for key in ['P4_WORKSPACE', 'P4_VOICE_MODEL', 'P4_WHISTLE_MODEL', 'P4_WHISTLE_SOURCES']:
            if key in env:
                log.write(key + '=' + env[key] + '\n')
        log.write('command: ' + ' '.join(command) + '\n\n'); log.flush()
        result = subprocess.run(command, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    content = (reports / 'native-build.txt').read_text()
    (reports / 'native-build.txt').write_text(re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', content))
    report = dict(compiled=False, physical_validation=False, build_exit_code=result.returncode,
        duration_seconds=time.time()-started, command=command,
        environment={k:env[k] for k in ['P4_WORKSPACE','P4_VOICE_MODEL','P4_WHISTLE_MODEL','P4_WHISTLE_SOURCES'] if k in env},
        repo_base_commit=git(REPO, 'rev-parse', 'HEAD'), branch=git(REPO, 'branch', '--show-current'),
        repo_has_local_changes=bool(git(REPO, 'status', '--porcelain')),
        toolchain='Zephyr SDK 1.0.1; riscv64-zephyr-elf GCC 14.3.0; rv32imafc_zicsr_zifencei / ilp32f',
        target='esp32p4_wifi6/esp32p4/hpcore', model_sha256=expected, modules={})
    for name, path in [('zephyr',a.workspace/'zephyr-robot-eyes'),
            ('tflite-micro',a.workspace/'optional/modules/lib/tflite-micro'),
            ('hal_espressif',a.workspace/'modules/hal/espressif')]:
        changed=git(path,'diff','--name-only').splitlines()
        report['modules'][name] = dict(commit=git(path,'rev-parse','HEAD'),
            local_changes=git(path,'status','--porcelain').splitlines(),
            local_modified_source_sha256={p:digest(path/p) for p in changed if (path/p).is_file()},
            local_diff_sha256=hashlib.sha256(git(path,'diff','--binary').encode()).hexdigest())
    app=REPO/'boards/waveshare_esp32p4_wifi6/zephyr'
    source_files=[p for p in app.rglob('*') if p.is_file() and p.suffix in ['.c','.cpp','.h','.inc','.conf','.overlay','.txt']]
    source_files += list((REPO/'common/kws').glob('*')) + list((PROJECT/'esp32p4/integration').glob('*'))
    source_files += [PROJECT/'esp32p4/build.sh',PROJECT/'scripts/prepare_firmware.py',
        REPO/'tools/prepare_p4_kws_frontend.py',REPO/'tools/prepare_p4_neural.py']
    report['source_sha256']={str(p.relative_to(REPO)):digest(p) for p in sorted(set(source_files)) if p.is_file()}
    save(reports/'native-build.json', report)
    if result.returncode:
        raise RuntimeError('Native compilation failed; see reports/native-build.txt')
    output=a.workspace/'build-p4-bilingual-kws/zephyr'
    elf_path=output/'zephyr.elf'; bin_path=output/'zephyr.bin'
    with elf_path.open('rb') as f:
        elf=ELFFile(f); symbols=elf.get_section_by_name('.symtab')
        start=symbols.get_symbol_by_name('p4_voice_model_start')[0]['st_value']
        end=symbols.get_symbol_by_name('p4_voice_model_end')[0]['st_value']
        if not 0x40000000 <= start < end <= 0x42000000:
            raise ValueError('Voice model is not mapped in P4 flash DROM')
        section=next(s for s in elf.iter_sections() if s['sh_addr'] <= start and end <= s['sh_addr']+s['sh_size'])
        if section['sh_flags'] & 1:
            raise ValueError('Voice model resides in writable memory')
        embedded=section.data()[start-section['sh_addr']:end-section['sh_addr']]
    if hashlib.sha256(embedded).hexdigest()!=expected or digest(model)!=expected:
        raise ValueError('Linked voice model differs from selected artifact')
    if len(bin_path.read_bytes()) > 0xfe0000-0x2000:
        raise ValueError('Image crosses existing reserved storage boundary')
    guarded=REPO/'build-artifacts/bilingual-kws/zephyr-checked.bin'
    guarded.parent.mkdir(parents=True,exist_ok=True)
    guard=json.loads(subprocess.check_output([sys.executable,str(REPO/'tools/p4_image_guard.py'),str(bin_path),str(guarded)],text=True))
    report.update(compiled=True, elf_sha256=digest(elf_path), image_sha256=digest(bin_path),
        image_bytes=bin_path.stat().st_size, voice_model_bytes=len(embedded),
        voice_model_start=hex(start),voice_model_end=hex(end),voice_model_flash_mapped=True,
        voice_model_section=section.name,voice_model_copied_to_psram=False,
        guarded_image=str(guarded),revision_guard=guard,
        physical_p4_latency_ms=None,total_runtime_ram_bytes=None,cpu_usage=None)
    regions={}
    for match in re.finditer(r'^\s*(\w+):\s+(\d+)\s+(B|KB|MB)\s+(\d+)\s+(B|KB|MB)\s+([\d.]+)%',content,re.MULTILINE):
        name,used,unit,size,sizeunit,percent=match.groups()
        units={'B':1,'KB':1024,'MB':1024*1024}
        regions[name]=dict(linker_used_bytes=int(used)*units[unit],
            region_bytes=int(size)*units[sizeunit],percent=float(percent))
    if not regions and previous.get('elf_sha256')==report['elf_sha256']:
        regions=previous.get('linker_memory_regions',{})
    report['linker_memory_regions']=regions
    report['linker_memory_note']='Static linker reservations; ext_dram includes the existing 16 MiB heap, from which voice arena/frontend are allocated. These regions overlap mapped views and must not be summed. Not measured runtime high-water RAM.'
    if a.whistle_model:
        report['whistle_link_check']=json.loads(subprocess.check_output([sys.executable,
            str(REPO/'tools/check_p4_whistle_image.py'),'--elf',str(elf_path),'--bin',str(bin_path)],text=True))
    save(reports/'native-build.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',type=Path,default=Path('/home/fred/microblocks-zephyr-work'))
    p.add_argument('--whistle-model',type=Path)
    p.add_argument('--whistle-sources',type=Path)
    run(p.parse_args())
