"""Fill short French phrase coverage with intelligible faster local speech.

No cropping or relabeling a sentence. Every retained waveform is the complete
requested command phrase. The normal-speed/long-phrase gap remains explicit.
"""
import importlib.metadata,json,hashlib,os
import numpy as np
from piper.voice import PiperVoice
from piper.config import SynthesisConfig
from common import DATA,WORDS,digest
from generate_tts import write_audio,PIPER_PIN
def run():
 path=DATA/'tts-models/fr_FR-mls-medium';v=PiperVoice.load(path,config_path=str(path)+'.json',use_cuda=True)
 if 'CUDAExecutionProvider' not in v.session.get_providers():raise RuntimeError('CUDA Piper required for this supplement')
 out=DATA/'manifests/tts-piper-phrases.jsonl'
 model_hash=digest(path)
 phrases=[(label,text) for label,texts in WORDS['fr'].items() for text in texts if ' ' in text]
 with out.open('w') as f:
  for speaker in range(24):
   partition='train' if speaker<16 else 'validation' if speaker<20 else 'test'
   for label,text in phrases:
    for speed in [1.3,1.5]:
     seed=20261030;np.random.seed(seed);name=hashlib.sha256(f'phrasefill:{speaker}:{text}:{speed}'.encode()).hexdigest()[:24]
     dest=DATA/'audio/tts'/f'{name}.wav'
     if not dest.exists():
      cfg=SynthesisConfig(speaker_id=speaker,length_scale=1/speed,noise_scale=.667,noise_w_scale=.8,normalize_audio=True)
      audio=np.concatenate([c.audio_float_array for c in v.synthesize(text,syn_config=cfg)]);write_audio(dest,audio,v.config.sample_rate)
     f.write(json.dumps(dict(path=str(dest),label=label,word=text,language='fr',source='Piper',kind='synthetic',engine_version=importlib.metadata.version('piper-tts'),
       voice=f'fr_FR-mls-medium:{speaker}',speaker=f'piper:fr_FR-mls-medium:{speaker}',split=partition,seed=seed,speed=speed,sha256=digest(dest),model_sha256=model_hash,model_revision=PIPER_PIN,license='CC-BY-4.0 dataset; retained model card',sample_rate=16000,
       note='complete phrase at 1.3x/1.5x; no phoneme cropping'))+'\n')
   f.flush();print('phrase supplement',speaker,partition,flush=True)
if __name__=='__main__':run()
