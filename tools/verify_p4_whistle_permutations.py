#!/usr/bin/env python3
"""Opt-in host C oracle over licensed local inputs, using synthetic PCM only.

This is numerical equivalence on the host, never P4 microphone/runtime proof.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from prepare_p4_whistle import prepare
from p4_whistle_permutations import permutations

ORACLE = r'''
#include <stdio.h>
#include WHISTLE_SOURCE
int main(int argc, char **argv) {
    if (argc != 4) return 90;
    FILE *f = fopen(argv[1], "rb"); if (!f) return 91;
    fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
    unsigned char *blob = malloc(size); if (!blob) return 92;
    if (fread(blob, 1, size, f) != (size_t)size) return 93; fclose(f);
    if (atoi(argv[3])) {
        nd_cact c; nd_tensor t;
        if (nd_cact_open(&c, blob, size) || nd_cact_tensor(&c, 10 + c.h4.num_layers * 27, &t)) return 94;
        /* Change one valid integer, leaving metadata untouched. */
        if (t.dtype == ND_DT_FP16) {
            uint16_t old; memcpy(&old, blob+t.offset, 2);
            uint16_t other = old == 0 ? 0x3c00 : 0;
            memcpy(blob+t.offset, &other, 2);
        } else if (t.dtype == ND_DT_FP32) {
            float old; memcpy(&old, blob+t.offset, 4);
            float other = old == 0 ? 1.0f : 0.0f;
            memcpy(blob+t.offset, &other, 4);
        } else return 95;
    }
    nd_whistle w; int rc = nd_whistle_open(&w, blob, size);
    if (atoi(argv[3])) { nd_whistle_close(&w); free(blob); return rc == -13 ? 0 : 96; }
    if (rc) return 97;
    f = fopen(argv[2], "wb"); if (!f) return 98;
    fwrite(s_perm1, sizeof(s_perm1), 1, f); fwrite(s_perm2, sizeof(s_perm2), 1, f);
    float pcm[1600]; for (int i=0; i<1600; ++i) pcm[i] = (float)((i*17)%101-50) / 100.0f;
    size_t count = (size_t)nd_whistle_frames(&w, 1600) * w.d;
    float *out = calloc(count, sizeof(float)); if (!out) return 99;
    if (nd_whistle_encode(&w, pcm, 1600, out)) return 100;
    for (size_t i=0; i<count; ++i) if (!isfinite(out[i])) return 101;
    fwrite(out, sizeof(float), count, f); fclose(f);
    free(out); nd_whistle_close(&w); free(blob); return 0;
}
'''


def verify(sources, model, output, cc='cc'):
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    report = {'physical_tested': False, 'audio': 'deterministic synthetic 1600-sample PCM; no recorded audio',
              'preparation': prepare(sources, model, output / 'generated'), 'commands': []}
    oracle = output / 'oracle.c'; oracle.write_text(ORACLE, encoding='utf-8', newline='\n')
    def run(args):
        p = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=120)
        report['commands'].append({'args': list(map(str, args)), 'returncode': p.returncode, 'stderr': p.stderr})
        if p.returncode: raise RuntimeError(p.stderr or f'Oracle exit {p.returncode}')
    for variant, source in [('original', sources / 'engine/src/nd_whistle.c'),
                            ('const', output / 'generated/nd_whistle_p4.c')]:
        binary = output / variant
        run([cc, '-O2', '-std=gnu99', '-I'+str(sources / 'engine/include'),
             '-DWHISTLE_SOURCE="'+str(source.resolve())+'"', oracle,
             *[sources / ('engine/src/'+name+'.c') for name in ('nd_cact', 'nd_quant', 'nd_tokenizer', 'nd_ledcmd')], '-lm', '-o', binary])
        run([binary, model, output / (variant+'.bin'), '0'])
    original = (output / 'original.bin').read_bytes()
    adapted = (output / 'const.bin').read_bytes()
    import struct
    expected = b''.join(struct.pack('<512i', *table) for table in permutations(model.read_bytes()))
    if original[:4096] != expected or original != adapted or len(original) <= 4096:
        raise ValueError('Original loader tables / encoder output differ')
    run([output / 'const', model, output / 'unused.bin', '1'])
    report.update(result='PASS', exact_table_values=1024, encoder_floats=(len(original)-4096)//4,
                  combined_sha256=hashlib.sha256(original).hexdigest(), mismatch_rejected=True,
                  seconds=time.monotonic()-start)
    (output/'receipt.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return {k:v for k,v in report.items() if k != 'commands'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for flag in ('sources', 'model', 'output'): parser.add_argument('--'+flag, type=Path, required=True)
    parser.add_argument('--cc', default='cc'); args=parser.parse_args()
    print(json.dumps(verify(args.sources, args.model, args.output, args.cc)))
