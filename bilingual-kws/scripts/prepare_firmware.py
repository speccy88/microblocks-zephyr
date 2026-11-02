"""Hash-check trusted model assets; invoked by CMake, no training dependency."""
import argparse,hashlib,json
from pathlib import Path
def verify_frontend(source,frontend):
 # Keep the training-checkout digest and a separately pinned LF source digest.
 raw_ok=hashlib.sha256(source).hexdigest()==frontend['adapter_sha256']
 lf_ok=hashlib.sha256(source.replace(b'\r\n',b'\n')).hexdigest()==frontend.get('adapter_lf_sha256')
 if not (raw_ok or lf_ok):raise ValueError('frontend changed since training; retrain/recalibrate instead of silently deploying')

def run(a):
 data=a.model.read_bytes();manifest=json.loads(a.model.with_suffix('.json').read_text())
 h=hashlib.sha256(data).hexdigest()
 if h!=manifest['model_sha256'] or len(data)!=manifest['model_bytes']:raise ValueError('model/manifest mismatch')
 if len(data)>150000:raise ValueError('model exceeds 150 KB firmware ceiling')
 if manifest['input']['shape']!=[1,118,40,1] or manifest['output']['shape']!=[1,10]:raise ValueError('tensor shape mismatch')
 if manifest['input']['dtype']!='int8' or manifest['output']['dtype']!='int8':raise ValueError('requires INT8 I/O')
 if manifest['labels']!=['UP','DOWN','LEFT','RIGHT','ANGRY','HAPPY','TIRED','NORMAL','UNKNOWN','SILENCE']:raise ValueError('semantic label order mismatch')
 if set(manifest['all_tensor_dtypes'])-{'int8','int32'}:raise ValueError('noninteger tensor')
 if manifest['tflm_commit']!='43b2a106a391dd8a099ac47f2ae858630a397264':raise ValueError('runtime pin mismatch')
 adapter=Path(__file__).resolve().parents[2]/'common/kws/features.c'
 verify_frontend(adapter.read_bytes(),manifest['frontend'])
 a.output.mkdir(parents=True,exist_ok=True);path=(a.output/'voice_model.bin').resolve();path.write_bytes(data)
 (a.output/'voice_assets.S').write_text('.section .rodata.p4_voice,"a"\n.balign 16\n.global p4_voice_model_start,p4_voice_model_end\np4_voice_model_start:\n.incbin '+json.dumps(path.as_posix())+'\np4_voice_model_end:\n')
 (a.output/'voice_assets.h').write_text('#pragma once\nextern "C" const unsigned char p4_voice_model_start[],p4_voice_model_end[];\n#define P4_VOICE_MODEL_BYTES '+str(len(data))+'\n#define P4_VOICE_OUTPUT_SCALE '+repr(float(manifest['output']['scale']))+'f\n#define P4_VOICE_OUTPUT_ZERO '+str(manifest['output']['zero_point'])+'\nstatic const unsigned char p4_voice_digest[32]={'+','.join(str(x) for x in bytes.fromhex(h))+'};\n')
 print(json.dumps(dict(model_sha256=h,bytes=len(data))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
