"""Capture actual machine/framework/GPU evidence without exposing identifiers."""
import os,platform,shutil,subprocess,time
from common import PROJECT,DATA,save
def run():
 DATA.mkdir(parents=True,exist_ok=True)
 import tensorflow as tf
 gpus=tf.config.list_physical_devices('GPU')
 for g in gpus:tf.config.experimental.set_memory_growth(g,True)
 with tf.device('/GPU:0'):
  x=tf.reduce_sum(tf.matmul(tf.ones((256,256)),tf.ones((256,256))))
 if not gpus or 'GPU:0' not in x.device:raise RuntimeError('actual CUDA operation required')
 save(PROJECT/'reports/preflight.json',dict(platform=platform.platform(),python=platform.python_version(),
   tensorflow=tf.__version__,cuda_probe_device=x.device,cuda_probe_result=float(x),
   gpu=[tf.config.experimental.get_device_details(g) for g in gpus],build_info=tf.sysconfig.get_build_info(),
   nvidia_smi=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv'],text=True),
   ram=subprocess.check_output(['free','-b'],text=True),disk_free_bytes=shutil.disk_usage(DATA).free,
   available_cpus=len(os.sched_getaffinity(0)),training_data_directory=str(DATA),
   note='Only training and host tests authorized. No board/serial access.'))
 print('CUDA GPU computation verified',x.device)
if __name__=='__main__':run()
