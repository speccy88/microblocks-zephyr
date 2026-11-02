"""Bounded waveform augmentation BEFORE the exact integer frontend."""
import numpy as np
from scipy.signal import lfilter,fftconvolve,resample
def augment(pcm,rng,noise=None):
 x=pcm.astype(np.float32)/32768;length=len(x)
 # Resampling changes both speed and pitch moderately (+/- ~1.2 semitones).
 # Independent phase-vocoder pitch shifting is deliberately not approximated.
 if rng.random()<.65:
  x=resample(x,int(len(x)*rng.uniform(.94,1.06))).astype(np.float32)
 if len(x)>length:
  start=(len(x)-length)//2;x=x[start:start+length]
 else:x=np.pad(x,((length-len(x))//2,(length-len(x)+1)//2))
 shift=int(rng.integers(-1600,1601));x=np.roll(x,shift)
 if shift>0:x[:shift]=0
 elif shift<0:x[shift:]=0
 x*=10**rng.uniform(-8/20,5/20)
 if rng.random()<.25:
  # Small random exponentially decaying room impulse, direct path dominant.
  n=int(rng.integers(160,1600));rir=rng.normal(0,1,n)*np.exp(-np.arange(n)/rng.uniform(150,500));rir[0]=4
  rir/=max(1,np.sum(np.abs(rir))*.25);x=fftconvolve(x,rir)[:length]
 if rng.random()<.3:
  # Mild microphone response / bandwidth variation.
  alpha=rng.uniform(.05,.45);x=lfilter([1-alpha],[1,-alpha],x)
  if rng.random()<.4:x=lfilter([1,-1],[1,-.96],x)
 if rng.random()<.75:
  n=rng.normal(0,1,length) if noise is None or rng.random()<.35 else noise[rng.integers(len(noise))].astype(np.float32)/32768
  if rng.random()<.3:n=lfilter([.2],[1,-.8],n)
  rms=np.sqrt(np.mean(x*x)+1e-10);nrms=np.sqrt(np.mean(n*n)+1e-10)
  x+=n*(max(rms,.003)/nrms)*10**(-rng.uniform(8,30)/20)
 if rng.random()<.15:
  clip=rng.uniform(.5,1);x=np.clip(x,-clip,clip)/clip
 if rng.random()<.1:x=np.round(x*2048)/2048
 return np.round(np.clip(x,-1,.999969)*32768).astype(np.int16)
