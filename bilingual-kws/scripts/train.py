"""Real local CUDA training, waveform augmentation, balanced semantic sampling."""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','1')
os.environ.setdefault('TF_NUM_INTRAOP_THREADS','2')
os.environ.setdefault('TF_NUM_INTEROP_THREADS','2')
os.environ.setdefault('OMP_NUM_THREADS','2')
import argparse,json,math,random,subprocess,time,threading
import numpy as np
import tensorflow as tf
from common import DATA,PROJECT,LABELS,save,digest
from frontend import window_features
from augment import augment

def model(name,classes=10,time_stride=2):
 L=tf.keras.layers;inputs=L.Input((118,40,1),batch_size=None,name='microfrontend')
 x=L.Rescaling(1/128)(inputs) # trained feature int8 values, not a second DSP frontend
 if name=='tinyconv':
  for width,kernel in [(16,5),(24,3),(32,3)]:
   x=L.Conv2D(width,kernel,strides=2,padding='same',use_bias=False)(x)
   x=L.BatchNormalization()(x);x=L.ReLU()(x)
 else:
  x=L.Conv2D(32,5,strides=(time_stride,2),padding='same',use_bias=False)(x)
  x=L.BatchNormalization()(x);x=L.ReLU()(x)
  for i,width in enumerate([64,80,96,96]):
   x=L.DepthwiseConv2D(3,strides=2 if i<2 else 1,padding='same',use_bias=False)(x)
   x=L.BatchNormalization()(x);x=L.ReLU()(x)
   x=L.Conv2D(width,1,use_bias=False)(x);x=L.BatchNormalization()(x);x=L.ReLU()(x)
 # DS-CNN keeps coarse frequency position; phonetic formants are not fully
 # frequency-translation invariant. Time is pooled to tolerate word placement.
 x=L.AveragePooling2D(pool_size=(int(x.shape[1]),int(x.shape[2]) if name=='tinyconv' else 1))(x)
 x=L.Flatten()(x);x=L.Dropout(.15)(x)
 out=L.Dense(classes,activation='softmax',dtype='float32',name='scores')(x)
 return tf.keras.Model(inputs,out,name=name)

def run(a):
 tf.keras.utils.set_random_seed(a.seed)
 tf.config.experimental.enable_op_determinism()
 gpus=tf.config.list_physical_devices('GPU')
 if not gpus:raise RuntimeError('GPU required; refusing a CPU-only training claim')
 for gpu in gpus:tf.config.experimental.set_memory_growth(gpu,True)
 # Explicit executed GPU proof, not merely enumerating the device.
 with tf.device('/GPU:0'):probe=tf.reduce_sum(tf.matmul(tf.ones((256,256)),tf.ones((256,256))))
 assert 'GPU:0' in probe.device
 records=json.loads((DATA/'prepared/records.json').read_text())
 def lexical_key(r):return r['label'] if r['label'] in ['UNKNOWN','SILENCE'] else r['language']+':'+r['word']
 lexicon=sorted({lexical_key(r) for r in records if r['split']=='train'}) if a.lexical else []
 lexical_targets={k:i for i,k in enumerate(lexicon)}
 pcm=np.load(DATA/'prepared/pcm.npy',mmap_mode='r')
 cached=np.load(DATA/'prepared/features.npy',mmap_mode='r')
 def eligible(r):return not (a.exclude_fast_phrases and r.get('note','').startswith('complete phrase at 1.3x/1.5x'))
 ids=[i for i,r in enumerate(records) if r['split']=='train' and eligible(r)]
 groups=[[i for i in ids if records[i]['label']==c] for c in LABELS]
 if not all(groups):raise ValueError('empty training action class')
 # Each semantic class sampled equally; human vs TTS 50/50 where both exist.
 human=[[i for i in g if records[i]['kind']=='human'] for g in groups]
 synthetic=[[i for i in g if records[i]['kind']=='synthetic'] for g in groups]
 cells=[]
 for g,h,s in zip(groups,human,synthetic):
  cells.append([([i for i in h if records[i]['language']==lang],[i for i in s if records[i]['language']==lang],[i for i in g if records[i]['language']==lang]) for lang in sorted({records[i]['language'] for i in g})])
 def by_language(indices):
  return [[i for i in indices if records[i]['language']==lang] for lang in sorted({records[i]['language'] for i in indices})]
 human=[by_language(g) for g in human];synthetic=[by_language(g) for g in synthetic];groups=[by_language(g) for g in groups]
 noise_ids=[i for i in ids if records[i]['label']=='SILENCE']
 noise=np.asarray(pcm[noise_ids])
 steps=a.steps or math.ceil(len(ids)/a.batch)
 rng=np.random.default_rng(a.seed)
 def batches():
  while True:
   xx=np.empty((a.batch,118,40,1),np.float32);yy=np.empty(a.batch,np.int32)
   for b in range(a.batch):
    if a.unknown_probability==.1:c=int(rng.integers(10))
    else:
     draw=rng.random();c=8 if draw<a.unknown_probability else 9 if draw<a.unknown_probability+.1 else int(rng.integers(8))
    if a.human_priority:
     h,s,g=cells[c][int(rng.integers(len(cells[c])))];tts_probability=.15 if len(h)>=200 else .3 if len(h)>=50 else .5
     pool=s if s and (not h or rng.random()<tts_probability) else h or g
    else:
     pool=human[c] if human[c] and (not synthetic[c] or rng.random()<.5) else synthetic[c] or groups[c]
     pool=pool[int(rng.integers(len(pool)))]
    i=int(pool[int(rng.integers(len(pool)))])
    if rng.random()<a.waveform_probability:
     wave=augment(pcm[i],rng,noise)
     context=noise[int(rng.integers(len(noise)))][:8000] if len(noise) and rng.random()<.5 else None
     xx[b,:,:,0]=window_features(wave,context)
    else:xx[b,:,:,0]=cached[i]
    yy[b]=lexical_targets[lexical_key(records[i])] if a.lexical else c
    if rng.random()<.35:
     t=int(rng.integers(0,110));xx[b,t:t+int(rng.integers(1,9)),:,0]=-128
     f=int(rng.integers(0,36));xx[b,:,f:f+int(rng.integers(1,5)),0]=-128
   yield xx,yy
 train=tf.data.Dataset.from_generator(batches,output_signature=(tf.TensorSpec((a.batch,118,40,1),tf.float32),tf.TensorSpec((a.batch,),tf.int32))).prefetch(2)
 val=np.load(DATA/'prepared/validation.npz');val_mask=np.array([eligible(records[i]) for i in val['ids']]);vx=val['x'][val_mask].astype(np.float32)[...,None];vy=val['y'][val_mask]
 counts=np.bincount(vy,minlength=10);val_weights=np.array([len(vy)/(10*max(1,counts[c])) for c in vy],np.float32)
 if a.lexical:vy=np.array([lexical_targets[lexical_key(records[i])] for i in val['ids'][val_mask]],np.int32)
 net=model(a.arch,len(lexicon) if a.lexical else 10,a.time_stride)
 net.compile(optimizer=tf.keras.optimizers.Adam(a.lr),loss='sparse_categorical_crossentropy',metrics=['accuracy'],jit_compile=False)
 out=PROJECT/'models'/a.name;out.mkdir(parents=True,exist_ok=True)
 if a.lexical:
  mapping={lexical_key(r):LABELS.index(r['label']) for r in records}
  save(out/'lexicon.json',dict(labels=lexicon,actions=[mapping[k] for k in lexicon]))
 callbacks=[tf.keras.callbacks.ModelCheckpoint(str(out/'best_checkpoint.keras'),monitor='val_loss',save_best_only=True),
  tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=a.patience,restore_best_weights=True),
  tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss',factor=.5,patience=3,min_lr=1e-5),
  tf.keras.callbacks.CSVLogger(str(out/'history.csv'))]
 gpu_samples=[];monitor_stop=threading.Event()
 def monitor():
  while not monitor_stop.is_set():
   try:gpu_samples.append(int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip()))
   except Exception:pass
   monitor_stop.wait(1)
 monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
 started=time.perf_counter();tf.config.experimental.reset_memory_stats('GPU:0')
 try:history=net.fit(train,steps_per_epoch=steps,epochs=a.epochs,validation_data=(vx,vy,val_weights),batch_size=a.batch,callbacks=callbacks,verbose=2)
 finally:monitor_stop.set();monitor_thread.join(timeout=3)
 elapsed=time.perf_counter()-started
 report=dict(architecture=a.arch,name=a.name,parameters=net.count_params(),epochs=len(history.history['loss']),
  seed=a.seed,batch_size=a.batch,steps_per_epoch=steps,learning_rate=a.lr,history=history.history,
  waveform_augmentation_probability=a.waveform_probability,
  unknown_sampling_probability=a.unknown_probability,
  human_priority=a.human_priority,
  first_time_stride=a.time_stride,
  exclude_fast_phrases=a.exclude_fast_phrases,training_records_used=len(ids),validation_records_used=len(vy),
  lexical_classes=len(lexicon) if a.lexical else None,
  training_seconds=elapsed,gpu_memory=tf.config.experimental.get_memory_info('GPU:0'),gpu_probe_device=probe.device,
  sampled_device_wide_peak_vram_mib=max(gpu_samples,default=None),gpu_memory_samples=len(gpu_samples),
  gpu_details=tf.config.experimental.get_device_details(gpus[0]),tensorflow=tf.__version__,
  build_info=tf.sysconfig.get_build_info(),dataset_sha256=digest(DATA/'prepared/records.json'),
  partition='speaker independent; model selection by validation loss only',
  gpu_nvidia_smi=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv'],text=True))
 save(PROJECT/'reports'/f'{a.name}-training.json',report)
 print(json.dumps({k:v for k,v in report.items() if k!='history'},indent=2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--arch',choices=['tinyconv','dscnn'],required=True);p.add_argument('--name',required=True)
 p.add_argument('--epochs',type=int,default=45);p.add_argument('--batch',type=int,default=64);p.add_argument('--steps',type=int,default=0)
 p.add_argument('--lr',type=float,default=.001);p.add_argument('--seed',type=int,default=20261030);p.add_argument('--patience',type=int,default=9)
 p.add_argument('--waveform-probability',type=float,default=.4)
 p.add_argument('--lexical',action='store_true')
 p.add_argument('--unknown-probability',type=float,default=.22)
 p.add_argument('--human-priority',action='store_true')
 p.add_argument('--time-stride',type=int,choices=[2,4],default=2)
 p.add_argument('--exclude-fast-phrases',action='store_true',help='reproduce the original TinyConv corpus stage even when supplemental clips are cached')
 run(p.parse_args())
