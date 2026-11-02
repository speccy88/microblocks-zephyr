"""Local licensed preset voices. No voice cloning or external speech APIs.

Piper MLS/LibriTTS speakers have disjoint train/validation/test IDs. Kokoro is
reserved entirely for engine-held-out testing; its scores never select a model.
"""
import argparse, importlib.metadata, json, math, os, random, wave
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from common import DATA, WORDS, digest
from download_datasets import download
PIPER_PIN='5041a7a49ae5b3a0f30e6837769eb03fdbb231bd'
KOKORO_PIN='f3ff3571791e39611d31c381e3a41a3af07b4987'
NEGATIVES={
 'en':['cat','dog','stop','go','yes','no','bed','bird','forward','backward','red','green','house','hot','cold','light','night','white','bright','height','high','upper','lower','laugh','tire','fire','sad','hungry','hungry again','the camera is ready','do not look at me','the weather is fine','please wait','what time is it','turn the lights off','I am talking to someone else'],
 'fr':['oui','non','arrête','avance','recule','chat','chien','maison','rouge','vert','chaud','froid','bonjour','merci','au revoir','grande','droits','droit','couche','marche','haute','basse','fatigue','colère','faim','triste','la caméra est prête','attends un moment','quelle heure est il','allume la lumière','je parle avec un ami','le temps est beau','ne bouge pas']}
def texts(lang):
 out=[]
 for action,words in WORDS[lang].items():
  out += [(action,w) for w in words]
  # Restrict phrase extensions to direction commands.
  if action in ['UP','DOWN','LEFT','RIGHT']:
   out.append((action,('look '+words[0]) if lang=='en' else ('regarde '+ ('en '+words[0] if action in ['UP','DOWN'] else 'à '+words[0]))))
 out += [('UNKNOWN',s) for s in NEGATIVES[lang]]
 return out
def write_audio(path,audio,rate):
 audio=np.asarray(audio,dtype=np.float32)
 audio=resample_poly(audio,16000,rate)
 sf.write(path,np.clip(audio,-1,1),16000,subtype='PCM_16')
def piper(a):
 from piper.voice import PiperVoice
 from piper.config import SynthesisConfig
 os.environ.setdefault('OMP_NUM_THREADS','2')
 models=[('fr','fr/fr_FR/mls/medium/fr_FR-mls-medium',a.voices),
         ('fr','fr/fr_FR/siwis/medium/fr_FR-siwis-medium',1),
         ('en','en/en_US/libritts/high/en_US-libritts-high',a.voices)]
 out=DATA/'manifests/tts-piper.jsonl';out.parent.mkdir(parents=True,exist_ok=True)
 rng=random.Random(20261030)
 with out.open('w') as f:
  for lang,model,count in models:
   url=f'https://huggingface.co/rhasspy/piper-voices/resolve/{PIPER_PIN}/{model}'
   path=download(url+'.onnx',DATA/'tts-models'/Path(model).name)
   config=download(url+'.onnx.json',str(path)+'.json')
   card=download(url.rsplit('/',1)[0]+'/MODEL_CARD',str(path)+'.MODEL_CARD')
   v=PiperVoice.load(str(path),config_path=str(config),use_cuda=a.cuda)
   if a.cuda and 'CUDAExecutionProvider' not in v.session.get_providers():raise RuntimeError('Piper CUDA requested but unavailable')
   model_hash=digest(path)
   for speaker in range(count):
    # Kokoro ff_siwis and Piper siwis share an underlying source speaker.
    # Keep BOTH in test, never train on Piper siwis then call Kokoro unseen.
    partition='test' if 'siwis' in model else 'train' if speaker<count-8 else 'validation' if speaker<count-4 else 'test'
    for label,text in texts(lang):
     for rep,speed in enumerate([0.88,1.0,1.12]):
      seed=rng.randrange(2**31);np.random.seed(seed)
      name=__import__('hashlib').sha256(f'{model}:{speaker}:{text}:{rep}'.encode()).hexdigest()[:24]
      dest=DATA/'audio/tts'/f'{name}.wav';dest.parent.mkdir(parents=True,exist_ok=True)
      if not dest.exists():
       cfg=SynthesisConfig(speaker_id=speaker,length_scale=1/speed,noise_scale=0.667,noise_w_scale=0.8,normalize_audio=True)
       chunks=list(v.synthesize(text,syn_config=cfg));audio=np.concatenate([c.audio_float_array for c in chunks]);write_audio(dest,audio,v.config.sample_rate)
      f.write(json.dumps(dict(path=str(dest),label=label,word=text,language=lang,source='Piper',kind='synthetic',
       engine_version=importlib.metadata.version('piper-tts'),voice=f'{Path(model).name}:{speaker}',speaker=f'piper:{Path(model).name}:{speaker}',
       split=partition,seed=seed,speed=speed,sha256=digest(dest),model_sha256=model_hash,model_revision=PIPER_PIN,
       license='CC-BY-4.0 dataset; see retained model card',sample_rate=16000,
       determinism='seed recorded; ONNX internal random generator may be nondeterministic'))+'\n')
    f.flush();print('Piper',lang,speaker,partition,flush=True)
def kokoro(a):
 # espeak-ng library is supplied by the separately installed loader wheel.
 import espeakng_loader
 os.environ['PHONEMIZER_ESPEAK_LIBRARY']=str(espeakng_loader.get_library_path())
 from phonemizer.backend.espeak.wrapper import EspeakWrapper
 EspeakWrapper.set_library(str(espeakng_loader.get_library_path()))
 from kokoro import KPipeline,KModel
 import torch
 torch.set_num_threads(2);torch.manual_seed(20261030)
 # Local snapshots pin both weight and voice downloads.
 from huggingface_hub import snapshot_download
 model_dir=snapshot_download('hexgrad/Kokoro-82M',revision=KOKORO_PIN,
   allow_patterns=['config.json','kokoro-v1_0.pth','voices/*.pt','LICENSE','VOICES.md'])
 model=KModel(config=str(Path(model_dir)/'config.json'),model=str(Path(model_dir)/'kokoro-v1_0.pth')).to('cuda').eval()
 out=DATA/'manifests/tts-kokoro.jsonl'
 with out.open('w') as f:
  for lang,code,voices in [('en','a',['af_heart','af_bella','am_adam','am_michael']),('fr','f',['ff_siwis'])]:
   pipeline=KPipeline(lang_code=code,model=model)
   for voice in voices:
    for label,text in texts(lang):
     for speed in [0.88,1.,1.12]:
      seed=20261030;torch.manual_seed(seed)
      name=__import__('hashlib').sha256(f'kokoro:{voice}:{text}:{speed}'.encode()).hexdigest()[:24];dest=DATA/'audio/tts'/f'{name}.wav'
      if not dest.exists():
       audio=np.concatenate([r.audio.cpu().numpy() for r in pipeline(text,voice=str(Path(model_dir)/'voices'/f'{voice}.pt'),speed=speed)])
       write_audio(dest,audio,24000)
      f.write(json.dumps(dict(path=str(dest),label=label,word=text,language=lang,source='Kokoro',kind='synthetic',
       engine_version=importlib.metadata.version('kokoro'),voice=voice,speaker='kokoro:'+voice,split='test',seed=seed,speed=speed,
       sha256=digest(dest),model_revision=KOKORO_PIN,license='Apache-2.0',sample_rate=16000))+'\n')
    f.flush();print('Kokoro held-out',voice,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--engine',choices=['piper','kokoro'],required=True);p.add_argument('--voices',type=int,default=24);p.add_argument('--cuda',action='store_true');a=p.parse_args();piper(a) if a.engine=='piper' else kokoro(a)
