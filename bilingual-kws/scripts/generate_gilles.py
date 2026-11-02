"""Additional French preset model, CC0 source; Kokoro remains held out."""
import importlib.metadata,json,hashlib
import numpy as np
from piper.voice import PiperVoice
from piper.config import SynthesisConfig
from common import DATA,digest
from generate_tts import texts,write_audio,PIPER_PIN
from download_datasets import download
def run():
 model='fr/fr_FR/gilles/low/fr_FR-gilles-low';url=f'https://huggingface.co/rhasspy/piper-voices/resolve/{PIPER_PIN}/{model}'
 path=download(url+'.onnx',DATA/'tts-models/fr_FR-gilles-low');cfg=download(url+'.onnx.json',str(path)+'.json');download(url.rsplit('/',1)[0]+'/MODEL_CARD',str(path)+'.MODEL_CARD')
 v=PiperVoice.load(path,config_path=str(cfg),use_cuda=True);model_hash=digest(path)
 missing={p for phrase in ['en colère','content','fatigué'] for sentence in v.phonemize(phrase) for p in sentence if p not in v.config.phoneme_id_map}
 if missing:raise RuntimeError(f'Rejected French voice: missing trained phonemes {sorted(missing)}; do not include its audio')
 out=DATA/'manifests/tts-piper-gilles.jsonl'
 with out.open('w') as f:
  for label,text in texts('fr'):
   for speed in [.9,1.1,1.3]:
    seed=20261030;np.random.seed(seed);name=hashlib.sha256(f'gilles:{text}:{speed}'.encode()).hexdigest()[:24];dest=DATA/'audio/tts'/f'{name}.wav'
    if not dest.exists():
     syn=SynthesisConfig(speaker_id=0,length_scale=1/speed,noise_scale=.667,noise_w_scale=.8,normalize_audio=True)
     audio=np.concatenate([c.audio_float_array for c in v.synthesize(text,syn_config=syn)]);write_audio(dest,audio,v.config.sample_rate)
    f.write(json.dumps(dict(path=str(dest),label=label,word=text,language='fr',source='Piper',kind='synthetic',engine_version=importlib.metadata.version('piper-tts'),
      voice='fr_FR-gilles-low:0',speaker='piper:fr_FR-gilles-low:0',split='train',seed=seed,speed=speed,sha256=digest(dest),model_sha256=model_hash,model_revision=PIPER_PIN,
      license='CC0 source dataset; retained model card',sample_rate=16000))+'\n')
   f.flush();print('Gilles',label,text,flush=True)
if __name__=='__main__':run()
