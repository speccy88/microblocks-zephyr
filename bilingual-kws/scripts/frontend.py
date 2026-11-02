"""Native microfrontend binding; no Python recreation of DSP arithmetic."""
import ctypes
import numpy as np
from common import DATA
_lib=None
def features(pcm):
 global _lib
 if _lib is None:
  _lib=ctypes.CDLL(str(DATA/'native/libkws_features.so'))
  _lib.kws_extract.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
  _lib.kws_extract.restype=ctypes.c_int
 pcm=np.ascontiguousarray(pcm,dtype=np.int16);out=np.empty((800,40),dtype=np.int8)
 n=_lib.kws_extract(pcm.ctypes.data,len(pcm),out.ctypes.data,len(out))
 if n<0:raise RuntimeError(f'native frontend failed {n}')
 return out[:n].copy()

def window_features(pcm,context=None):
 """Window from a running frontend, with explicit preceding context.

 Validation uses 500 ms quiet context. Training varies that context. Firmware
 maintains the same state continuously; stream evaluation must use whole streams.
 """
 if context is None:context=np.zeros(8000,np.int16)
 return features(np.concatenate([context,pcm]))[-118:]

class Stream:
 def __init__(self):
  features(np.zeros(480,np.int16)) # initialize the shared library binding
  _lib.kws_stream_push.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
  _lib.kws_stream_push.restype=ctypes.c_int
  if not _lib.kws_stream_begin():raise RuntimeError('frontend already owned')
 def push(self,pcm):
  pcm=np.ascontiguousarray(pcm,dtype=np.int16);out=np.empty((101,40),np.int8)
  n=_lib.kws_stream_push(pcm.ctypes.data,len(pcm),out.ctypes.data,len(out))
  if n<0:raise RuntimeError(f'stream frontend failed {n}')
  return out[:n].copy()
 def close(self):_lib.kws_stream_end()
