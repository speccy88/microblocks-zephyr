"""Static TFLite Conv/DW/FC MAC census; no latency inference from clock rates."""
import argparse,json
from pathlib import Path
import numpy as np
from tensorflow.lite.python import schema_py_generated as s
def run(path):
 model=s.Model.GetRootAsModel(path.read_bytes(),0);graphs=[]
 for gi in range(model.SubgraphsLength()):
  g=model.Subgraphs(gi);macs=0
  def shape(index):return np.asarray(g.Tensors(index).ShapeAsNumpy(),np.int64)
  for j in range(g.OperatorsLength()):
   op=g.Operators(j);code=model.OperatorCodes(op.OpcodeIndex()).BuiltinCode()
   if code==s.BuiltinOperator.CONV_2D:
    w=shape(op.Inputs(1));macs+=int(np.prod(shape(op.Outputs(0)))*np.prod(w[1:]))
   elif code==s.BuiltinOperator.DEPTHWISE_CONV_2D:
    w=shape(op.Inputs(1));macs+=int(np.prod(shape(op.Outputs(0)))*w[1]*w[2])
   elif code==s.BuiltinOperator.FULLY_CONNECTED:
    w=shape(op.Inputs(1));macs+=int(np.prod(shape(op.Outputs(0)))*w[-1])
  graphs.append(dict(subgraph=gi,static_conv_dw_fc_macs=macs))
 print(json.dumps(dict(model=path.name,graphs=graphs,scope='static operation count; excludes runtime control flow/frontend/memory and is NOT device latency'),indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('model',type=Path);run(p.parse_args().model)
