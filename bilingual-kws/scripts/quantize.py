"""Full integer conversion using only training audio for calibration."""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import argparse,json,yaml
from pathlib import Path
import numpy as np
import tensorflow as tf
from common import DATA,PROJECT,LABELS,save,digest
from frontend import window_features
def run(a):
 tf.config.set_visible_devices([], 'GPU') # conversion/calibration is CPU work
 net=tf.keras.models.load_model(a.checkpoint)
 lexical_file=a.checkpoint.parent/'lexicon.json';lexical=None
 if lexical_file.exists():
  lexical=json.loads(lexical_file.read_text());mapping=np.zeros((len(lexical['labels']),10),np.float32)
  for j,action in enumerate(lexical['actions']):mapping[j,action]=1
  action_scores=tf.keras.layers.Dense(10,use_bias=False,trainable=False,kernel_initializer=tf.keras.initializers.Constant(mapping),name='semantic_probabilities')(net.output)
  net=tf.keras.Model(net.input,action_scores,name=net.name+'_semantic')
 records=json.loads((DATA/'prepared/records.json').read_text());pcm=np.load(DATA/'prepared/pcm.npy',mmap_mode='r');rng=np.random.default_rng(20261030)
 ids=[]
 for label in LABELS:
  candidates=[i for i,r in enumerate(records) if r['split']=='train' and r['label']==label]
  # Retain human data explicitly in each action when available.
  real=[i for i in candidates if records[i]['kind']=='human']
  synth=[i for i in candidates if records[i]['kind']!='human']
  for pool in [real,synth]:
   for lang in sorted({records[i]['language'] for i in pool}):
    cell=[i for i in pool if records[i]['language']==lang]
    ids.extend(rng.choice(cell,min(len(cell),25),replace=False).tolist())
 def calibration():
  for i in ids:yield [window_features(pcm[i]).astype(np.float32)[None,...,None]]
 @tf.function(input_signature=[tf.TensorSpec([1,118,40,1],tf.float32,name='microfrontend')])
 def infer(x):return net(x,training=False)
 # Freeze Keras 3 resource variables explicitly. Passing the live Keras model
 # with this concrete signature leaves READ_VARIABLE in some TF 2.20 graphs.
 from tensorflow.python.framework.convert_to_constants import convert_variables_to_constants_v2
 frozen=convert_variables_to_constants_v2(infer.get_concrete_function())
 converter=tf.lite.TFLiteConverter.from_concrete_functions([frozen])
 converter.optimizations=[tf.lite.Optimize.DEFAULT];converter.representative_dataset=calibration
 converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
 converter.inference_input_type=tf.int8;converter.inference_output_type=tf.int8
 data=converter.convert();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(data)
 i=tf.lite.Interpreter(model_content=data,num_threads=2);i.allocate_tensors()
 inputs=i.get_input_details();outputs=i.get_output_details();tensors=i.get_tensor_details()
 assert inputs[0]['shape'].tolist()==[1,118,40,1] and outputs[0]['shape'].tolist()==[1,10]
 assert inputs[0]['dtype']==np.int8 and outputs[0]['dtype']==np.int8
 assert not any(t['dtype'] in [np.float32,np.float16,np.float64] for t in tensors),'hidden floating tensor'
 ops=sorted({o['op_name'] for o in i._get_ops_details() if o['op_name']!='DELEGATE'})
 allowed={'CONV_2D','DEPTHWISE_CONV_2D','AVERAGE_POOL_2D','RESHAPE','FULLY_CONNECTED','SOFTMAX','MUL','QUANTIZE'}
 if set(ops)-allowed:raise ValueError(f'unverified operator {set(ops)-allowed}')
 def tensor(t):return dict(shape=t['shape'].tolist(),dtype=str(t['dtype'].__name__),scale=float(t['quantization'][0]),zero_point=int(t['quantization'][1]))
 macs=0
 for layer in net.layers:
  if isinstance(layer,tf.keras.layers.Conv2D):macs+=int(np.prod(layer.output.shape[1:])*np.prod(layer.kernel_size)*int(layer.input.shape[-1]))
  elif isinstance(layer,tf.keras.layers.DepthwiseConv2D):macs+=int(np.prod(layer.output.shape[1:])*np.prod(layer.kernel_size))
  elif isinstance(layer,tf.keras.layers.Dense):macs+=int(layer.input.shape[-1])*layer.units
 manifest=dict(schema_version=1,model_sha256=digest(a.output),model_bytes=len(data),labels=LABELS,
  languages=['en','fr'],floating_checkpoint_sha256=digest(a.checkpoint),
  output_semantics='sum of lexical Softmax probabilities by action' if lexical else 'direct ten-class Softmax',
  lexical_labels=lexical['labels'] if lexical else None,
  input=tensor(inputs[0]),output=tensor(outputs[0]),operators=ops,parameters=net.count_params(),
  estimated_multiply_accumulates=macs,mac_scope='static Conv2D/DepthwiseConv2D/Dense products per window; excludes frontend, activation, normalization, Softmax and memory overhead',
  calibration_samples=len(ids),calibration_human_samples=sum(records[j]['kind']=='human' for j in ids),
  calibration_split='train only',dataset_manifest_sha256=digest(PROJECT/'datasets/dataset_manifest.json'),
  frontend=json.loads((DATA/'native/frontend.json').read_text()),
  frontend_contract=str('configs/training.yaml'),all_tensor_dtypes=sorted({t['dtype'].__name__ for t in tensors}),
  frontend_settings=yaml.safe_load((PROJECT/'configs/training.yaml').read_text())['frontend'],
  dataset_provenance=dict(manifest='datasets/dataset_manifest.json',human_sources=['Google Speech Commands v0.02 (CC-BY-4.0)','MLCommons MSWC 1.0 (CC-BY-4.0)'],synthetic_sources=['Piper MLS/LibriTTS','Kokoro (test engine only)']),
  tflm_commit='43b2a106a391dd8a099ac47f2ae858630a397264',
  firmware_requirements=dict(native_zephyr=True,dedicated_kws_backend=True,generic_dense_loader_compatible=False,arena_target_bytes=131072),
  physical_validation=False)
 save(a.output.with_suffix('.json'),manifest);print(json.dumps(manifest,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
