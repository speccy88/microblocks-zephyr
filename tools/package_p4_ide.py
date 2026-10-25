#!/usr/bin/env python3
"""Package genuine pinned GP editor with native P4 camera blocks and preview."""
# SPDX-License-Identifier: MPL-2.0
import argparse,hashlib,json,re
from pathlib import Path
from patch_ide import patch_ide
from fruit_jam_ide_assets import prepare_assets

def patch_p4(js,data,repo):
 from package_pages import project_api
 board=repo/'boards/waveshare_esp32p4_wifi6/integration'
 js,data=patch_ide(js,data,(board/'P4_Camera.ubl').read_bytes())
 source=js.decode();m=re.search(r'loadPackage\((\{"files":\[.*?\],"remote_package_size":\d+\})\)',source)
 meta=json.loads(m[1]);out=bytearray();files=[]
 for item in meta['files']:
  name=item['filename'];payload=data[item['start']:item['end']]
  if name.endswith('/MicroBlocksRuntime.gp'):
   anchor=b"\t\t\topenSerialPort 'webserial' 115200\n\t\t\tportName = 'webserial'"
   if payload.count(anchor)!=1:raise ValueError('Changed GP WebSerial startup anchor')
   # Like GP's firmware installer, yield while the asynchronous browser port
   # opens. Sending immediately makes sendMsg close the not-yet-open port.
   wait=(b"\t\t\topenSerialPort 'webserial' 115200\n"
     b"\t\t\topenStart = (msecsSinceStart)\n"
     b"\t\t\twhile (and (not (isOpenSerialPort 1)) (((msecsSinceStart) - openStart) < 5000)) {\n"
     b"\t\t\t\twaitMSecs 10\n\t\t\t}\n"
     b"\t\t\tif (not (isOpenSerialPort 1)) {\n"
     b"\t\t\t\tcloseSerialPort 1\n\t\t\t\tdisconnected = true\n\t\t\t\treturn\n\t\t\t}\n"
     b"\t\t\tportName = 'webserial'")
   payload=payload.replace(anchor,wait)
   for method in [b'boardIsBLECapable',b'boardHasFileSystem']:
    header=b'method '+method+b' SmallRuntime {\n'
    if payload.count(header)!=1:raise ValueError('Changed GP board capability anchor')
    payload=payload.replace(header,header+b"\tif (and (notNil boardType) (beginsWith boardType 'Waveshare ESP32-P4')) { return false }\n")
  for before,after in [(b"atPut primsets 'rlcd'",b"atPut primsets 'p4'"),(b'rlcd.loadLibrary',b'p4.loadLibrary'),(b'rlcd.openExample',b'p4.openExample'),(b'Waveshare_RLCD_4_2.ubl',b'P4_Camera.ubl'),(b'Waveshare RLCD 4.2',b'P4 Camera'),(b'Examples/Waveshare/',b'Examples/P4/')]:payload=payload.replace(before,after)
  payload=payload.replace(b"'arithmetic' 'output'",b"'arithmetic' 'output' 'camera-pipeline'")
  name=name.replace('Waveshare_RLCD_4_2.ubl','P4_Camera.ubl').replace('Examples/Waveshare/','Examples/P4/')
  start=len(out);out.extend(payload);files.append(dict(filename=name,start=start,end=len(out)))
 payload=(board/'camera-pipeline.ubp').read_bytes()+b'\n'+(board/'P4_Camera.ubl').read_bytes()
 start=len(out);out.extend(payload);files.append(dict(filename='/Examples/P4/camera-pipeline.ubp',start=start,end=len(out)))
 source=source[:m.start(1)]+json.dumps(dict(files=files,remote_package_size=len(out)),separators=(',',':'))+source[m.end(1):]
 source=source.replace('"/Examples","Waveshare"','"/Examples","P4"')
 return project_api(source.encode(),bytes(out))

def adapter(repo):
 text=(repo/'web/portal/portal-adapter.js').read_text()
 text=text.replace("const isP2=profile.board==='propeller2';","const isP4=profile.board==='esp32p4',isP2=profile.board==='propeller2';")
 text=text.replace('const filters=profile.board',"const filters=isP4?[{usbVendorId:0x1a86},{usbVendorId:0x303a}]:profile.board")
 text=text.replace('isP2?', '(isP2||isP4)?').replace('||isP2;', '||isP2||isP4;').replace('if(!isP2)panel.append(local);ip.hidden=isP2;', 'if(!isP2&&!isP4)panel.append(local);ip.hidden=isP2||isP4;')
 text=text.replace("if(mode&&mode.value==='wifi'){", "if(profile.bridge||mode&&mode.value==='wifi'){")
 text=text.replace('const url=new URL(endpoint.value);',"const url=new URL(profile.bridge?location.origin.replace('http:','ws:')+'/ws/vm':endpoint.value);")
 text=text.replace("if(url.protocol!=='wss:'||url.username", "if((url.protocol!=='wss:'&&!(profile.bridge&&url.protocol==='ws:'&&url.hostname==='127.0.0.1'))||url.username")
 text=text.replace("if(frame[0]===251&&frame[1]===205){", "if(frame[0]===251&&(frame[1]===206||frame[1]===207)){window.P4CameraAccept?.(frame);}else if(frame[0]===251&&frame[1]===205){")
 text=text.replace('window.hasWebSerial=()=>true;', 'window.P4Send=write;window.hasWebSerial=()=>true;')
 text=text.replace("'propeller2':'p2'", "'propeller2':'p2','esp32p4':'p4'")
 text=text.replace("'propeller2':'Parallax P2'", "'propeller2':'Parallax P2','esp32p4':'Waveshare ESP32-P4'")
 # GP emits the disconnected label while a transport is opening. Only check
 # an actual board identity, otherwise the ready handshake closes itself.
 text=text.replace("const type=event.detail.value;if(!type)return;", "const type=event.detail.value;if(!type||type==='Connect')return;")
 text=text.replace("['output','50 outputs']", "['output','50 outputs'],['camera-pipeline','Camera grayscale preview']")
 text=text.replace("const lanNote=element('p',(isP2||isP4)?", "const lanNote=element('p',isP4?'P4 runs native Zephyr. USB programming and local image preview are available. Board Wi-Fi hosting is not enabled.':isP2?")
 return text.encode()

def build(source,output,repo):
 manifest=json.loads((repo/'dependencies/ide-assets.json').read_text());assets={}
 for item in manifest['files']:
  raw=(source/item['path']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Changed source: '+item['path'])
  assets[item['path']]=raw
 common=prepare_assets(repo,source);js,data=patch_p4(assets['gp_wasm.js'],assets['gp_wasm.data'],repo)
 assets.update(common);assets['gp_wasm.js']=js;assets['gp_wasm.data']=data
 assets['portal-core.js']=(repo/'web/portal/portal-core.js').read_bytes();assets['portal.css']=(repo/'web/portal/portal.css').read_bytes()
 assets['unoq-network.js']=adapter(repo);assets['p4-camera.js']=(repo/'web/p4-camera.js').read_bytes()
 html=assets['microblocks.html'].decode();tag='<script src="unoq-network.js"></script>'
 assert html.count(tag)==1
 html=html.replace(tag,'<link rel="stylesheet" href="portal.css"><script>window.PORTAL_BOARD={board:"esp32p4",name:"Waveshare ESP32-P4 camera",bridge:location.hostname==="127.0.0.1"&&new URLSearchParams(location.search).get("bridge")==="1"};</script><script src="portal-core.js"></script>'+tag+'<script src="p4-camera.js"></script>')
 # Match the physically accepted editor startup: wait for local English assets.
 gate=b"Module.preRun.push(function(){addRunDependency('board-english');Promise.resolve(GetText.ready).then(function(){removeRunDependency('board-english');});});\n"
 assets['gp_wasm.js']=gate+js
 assets['microblocks.html']=html.encode()
 output.mkdir(parents=True,exist_ok=True)
 for name,raw in assets.items():target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 report=dict(real_editor='MicroBlocks GP 2.5.8',files=len(assets),p4_library_sha256=hashlib.sha256((repo/'boards/waveshare_esp32p4_wifi6/integration/P4_Camera.ubl').read_bytes()).hexdigest(),gp_data_sha256=hashlib.sha256(data).hexdigest(),runtime_external_network=False)
 (output/'p4-editor-manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--ide-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(build(a.ide_source,a.output,Path(__file__).resolve().parents[1]),indent=2))
