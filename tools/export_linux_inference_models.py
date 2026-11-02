#!/usr/bin/env python3
"""Export one authored PyTorch CPU network to separate ONNX and LiteRT assets.

Development tool only. No pretrained weights, network fetch, torch.load/pickle,
accelerator, board install or robot operation. Install optional export tooling.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile

def export(output):
    import torch
    import litert_torch
    torch.set_num_threads(1)
    output=Path(output)
    if output.exists() and any(output.iterdir()) and not (output/'.authored-inference-demo').is_file():raise ValueError('Choose a fresh output or the owned authored-demo directory')
    output.mkdir(parents=True,exist_ok=True)
    model=torch.nn.Sequential(torch.nn.Linear(4,4),torch.nn.ReLU(),torch.nn.Linear(4,3)).eval()
    with torch.no_grad():
        model[0].weight.copy_(torch.tensor([[1.,-.5,0.,.25],[0.,1.,-.25,0.],[.5,0.,1.,-.5],[-1.,.5,.25,1.]]))
        model[0].bias.copy_(torch.tensor([.1,.2,.3,.4]))
        model[2].weight.copy_(torch.tensor([[.5,-1.,2.,0.],[1.,0.,0.,-.5],[-1.,.25,.5,1.]]))
        model[2].bias.copy_(torch.tensor([.25,-.75,1.5]))
    sample=torch.tensor([[1.,2.,3.,4.]],dtype=torch.float32)
    expected=model(sample).detach().tolist()[0]
    with tempfile.TemporaryDirectory(prefix='inference-export-',dir=output.parent) as folder:
        stage=Path(folder)
        torch.onnx.export(model,(sample,),stage/'tiny-dense.onnx',input_names=['features'],output_names=['scores'],opset_version=18,dynamo=True,external_data=False)
        import onnx
        exported=onnx.load_model(stage/'tiny-dense.onnx',load_external_data=False)
        pending=[exported]
        while pending:
            message=pending.pop()
            for field,value in list(message.ListFields()):
                if field.name in ('doc_string','metadata_props'):
                    message.ClearField(field.name) # export traces contain host-specific source/cache paths
                elif field.type==field.TYPE_MESSAGE:pending.extend(value if field.is_repeated else [value])
        onnx.save_model(exported,stage/'tiny-dense.onnx',save_as_external_data=False)
        converted=litert_torch.convert(model,(sample,))
        converted.export(str(stage/'tiny-dense.tflite'))
        variants={name:{'file':'tiny-dense.'+format,'format':format,'sha256':hashlib.sha256((stage/('tiny-dense.'+format)).read_bytes()).hexdigest()} for name,format in [('onnx','onnx'),('litert','tflite')]}
        versions={n:importlib.metadata.version(n) for n in ['torch','litert-torch','ai-edge-litert','onnx','onnxscript']}
        catalog={'schema':1,'license':'MIT; authored source and fixed weights in this repository','source':'tools/export_linux_inference_models.py',
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'export_versions':versions,
            'models':{'tiny-dense-v1':{'input':{'shape':[1,4],'dtype':'float32'},'output':{'shape':[1,3],'dtype':'float32'},'variants':variants}},
            'fixture':{'input':[1,2,3,4],'input_scale':1000,'scaled_input':[1000,2000,3000,4000],'expected_float32':expected,'output_scale':1000,'expected_scaled':[round(v*1000) for v in expected],'absolute_tolerance':0.00001,
                       'scope':'Tiny authored two-dense-layer ReLU network. Integration fixture, not vision/speech accuracy or a performance benchmark.'}}
        (stage/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8')
        for path in stage.iterdir():
            if path.name not in ['tiny-dense.onnx','tiny-dense.tflite','catalog.json']:raise ValueError('Unexpected external export artifact')
        for path in stage.iterdir():path.replace(output/path.name)
    (output/'.authored-inference-demo').write_text('Authored MIT PyTorch model fixtures; see export source and catalog.\n',encoding='utf-8')
    print(json.dumps({'output':str(output),'versions':versions,'variants':variants,'expected':expected}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();export(a.output)
