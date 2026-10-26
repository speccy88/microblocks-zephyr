#!/usr/bin/env python3
"""Package genuine pinned GP editor with native P4 camera blocks and preview."""
# SPDX-License-Identifier: MPL-2.0
import argparse,hashlib,json,re
from pathlib import Path
from patch_ide import patch_ide
from patch_p4_media import patch_source
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
  audio_anchor=b"if (notNil data) { importLibraryFromString scripter data 'P4 Camera' '' }"
  if audio_anchor in payload:
   payload=payload.replace(audio_anchor,audio_anchor+b"\n\t\tdata = (readEmbeddedFile 'Libraries/P4_Audio.ubl')\n\t\tif (notNil data) { importLibraryFromString scripter data 'P4 Audio' '' }\n\t\tdata = (readEmbeddedFile 'Libraries/P4_Speech.ubl')\n\t\tif (notNil data) { importLibraryFromString scripter data 'P4 Local Speech' '' }\n\t\tdata = (readEmbeddedFile 'Libraries/P4_Neural.ubl')\n\t\tif (notNil data) { importLibraryFromString scripter data 'P4 Neural Networks' '' }")
  payload=payload.replace(b"'output' 'camera-pipeline'",b"'output' 'camera-pipeline' 'audio-levels' 'local-speech' 'neural-sine' 'neural-custom'")
  if name.endswith('.gp'):payload=patch_source(name,payload,repo)
  name=name.replace('Waveshare_RLCD_4_2.ubl','P4_Camera.ubl').replace('Examples/Waveshare/','Examples/P4/')
  start=len(out);out.extend(payload);files.append(dict(filename=name,start=start,end=len(out)))
 payload=(board/'P4_Audio.ubl').read_bytes();start=len(out);out.extend(payload);files.append(dict(filename='/Libraries/P4_Audio.ubl',start=start,end=len(out)))
 payload=(board/'P4_Speech.ubl').read_bytes();start=len(out);out.extend(payload);files.append(dict(filename='/Libraries/P4_Speech.ubl',start=start,end=len(out)))
 payload=(board/'P4_Neural.ubl').read_bytes();start=len(out);out.extend(payload);files.append(dict(filename='/Libraries/P4_Neural.ubl',start=start,end=len(out)))
 for example in ['camera-pipeline','audio-levels','local-speech','neural-sine','neural-custom']:
  payload=(board/(example+'.ubp')).read_bytes()+b'\n'+(board/'P4_Camera.ubl').read_bytes()+b'\n'+(board/'P4_Audio.ubl').read_bytes()+b'\n'+(board/'P4_Speech.ubl').read_bytes()+b'\n'+(board/'P4_Neural.ubl').read_bytes()
  start=len(out);out.extend(payload);files.append(dict(filename='/Examples/P4/'+example+'.ubp',start=start,end=len(out)))
 source=source[:m.start(1)]+json.dumps(dict(files=files,remote_package_size=len(out)),separators=(',',':'))+source[m.end(1):]
 source=source.replace('"/Examples","Waveshare"','"/Examples","P4"')
 return project_api(source.encode(),bytes(out))

def adapter(repo):
 text=(repo/'web/portal/portal-adapter.js').read_text()
 text=text.replace("const isP2=profile.board==='propeller2';","const isP4=profile.board==='esp32p4',isP2=profile.board==='propeller2';")
 text=text.replace('const filters=profile.board',"const filters=isP4?[{usbVendorId:0x1a86},{usbVendorId:0x303a}]:profile.board")
 text=text.replace('isP2?', '(isP2||isP4)?').replace('||isP2;', '||isP2||isP4;').replace('if(!isP2)panel.append(local);ip.hidden=isP2;', 'if(!isP2&&!isP4)panel.append(local);ip.hidden=isP2||isP4;')
 text=text.replace("if(mode&&mode.value==='wifi'){", "if(profile.bridge||mode&&mode.value==='wifi'){")
 text=text.replace('const url=new URL(endpoint.value);',"const url=new URL(profile.bridge||profile.hosted?location.origin.replace('http:','ws:')+'/ws/vm':endpoint.value);")
 text=text.replace("if(url.protocol!=='wss:'||url.username", "if((url.protocol!=='wss:'&&!(profile.bridge&&url.protocol==='ws:'&&url.hostname==='127.0.0.1')&&!(profile.hosted&&location.protocol==='http:'&&location.hostname==='192.168.4.1'&&url.href===location.origin.replace('http:','ws:')+'/ws/vm'))||url.username")
 text=text.replace("if(frame[0]===251&&frame[1]===205){", "if(frame[0]===251&&frame[1]===216){window.P4NeuralAccept?.(frame);}else if(frame[0]===251&&(frame[1]===208||frame[1]===209)){}else if(frame[0]===251&&(frame[1]===206||frame[1]===207)){window.P4CameraAccept?.(frame);}else if(frame[0]===251&&frame[1]===205){")
 frame_anchor='const frame=assembly.slice(0,size);assembly=assembly.slice(size);'
 if text.count(frame_anchor)!=1:raise ValueError('Changed bounded frame transport anchor')
 # Local read-only observers support result views and acceptance checks.
 # Copy the frame so a consumer cannot mutate the GP transport queue.
 text=text.replace(frame_anchor,frame_anchor+"window.dispatchEvent(new CustomEvent('p4-vm-frame',{detail:frame.slice()}));")
 text=text.replace('window.hasWebSerial=()=>true;', 'window.P4Send=write;window.hasWebSerial=()=>true;')
 text=text.replace("'propeller2':'p2'", "'propeller2':'p2','esp32p4':'p4'")
 text=text.replace("'propeller2':'Parallax P2'", "'propeller2':'Parallax P2','esp32p4':'Waveshare ESP32-P4'")
 # GP emits the disconnected label while a transport is opening. Only check
 # an actual board identity, otherwise the ready handshake closes itself.
 text=text.replace("const type=event.detail.value;if(!type)return;", "const type=event.detail.value;if(!type||type==='Connect')return;")
 text=text.replace("['output','50 outputs']", "['output','50 outputs'],['camera-pipeline','Camera grayscale preview']")
 text=text.replace("['camera-pipeline','Camera grayscale preview']", "['camera-pipeline','Camera grayscale preview'],['audio-levels','Bounded PCM levels'],['local-speech','Local speech (model profile required)'],['neural-sine','Neural network: sine demo'],['neural-custom','Imported sensor-affine model (import fixture first)']")
 text=text.replace("const lanNote=element('p',(isP2||isP4)?", "const lanNote=element('p',profile.hosted?'This editor is served by your board on your approved Wi-Fi network. Connect using its same-origin WebSocket, or select USB on a supported desktop browser.':isP4?'P4 runs native Zephyr. USB programming and local media preview are available. The station-hosted target uses the board address assigned by your network.':isP2?")
 text=text.replace("(isP2||isP4)?[['usb','USB Web Serial']]", "profile.hosted?[['wifi','Board Wi-Fi WebSocket'],['usb','USB Web Serial']]:(isP2||isP4)?[['usb','USB Web Serial']]")
 text=text.replace("endpoint.hidden=mode.value!=='wifi';", "endpoint.hidden=profile.hosted||mode.value!=='wifi';")
 text=text.replace("Choose Connect to select your USB board.", "Choose Connect to program your board.")
 return text.encode()

def media_assets(assets,html,repo):
 for name in ['p4-media-core.js','p4-media.js','p4-media.css','p4-neural-core.js','p4-neural.js','p4-neural.css','p4-neural-catalog.json']:
  assets[name]=(repo/'web'/name).read_bytes()
 tags=[]
 for name in ['p4-media.css','p4-media-core.js','p4-media.js','p4-neural.css','p4-neural-core.js','p4-neural.js']:
  url=name+'?v='+hashlib.sha256(assets[name]).hexdigest()[:16]
  tags.append('<link rel="stylesheet" href="'+url+'">' if name.endswith('.css') else '<script src="'+url+'"></script>')
 html=html.replace('</head>','\n'.join(tags)+'\n</head>')
 # The P4 adapter evolves independently of the shared portal assets.
 html=re.sub(r'src="unoq-network.js(?:\?v=[^"]*)?"','src="unoq-network.js?v='+hashlib.sha256(assets['unoq-network.js']).hexdigest()[:16]+'"',html)
 return html

def build(source,output,repo,hosted=False):
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
 if hosted:html=html.replace('bridge:location.hostname==="127.0.0.1"&&new URLSearchParams(location.search).get("bridge")==="1"','hosted:true,bridge:false')
 # Match the physically accepted editor startup: wait for local English assets.
 gate=b"Module.preRun.push(function(){addRunDependency('board-english');Promise.resolve(GetText.ready).then(function(){removeRunDependency('board-english');});});\n"
 assets['gp_wasm.js']=gate+js
 html=media_assets(assets,html,repo)
 html=html.replace('26eb855451371f4c',hashlib.sha256(assets['gp_wasm.js']+data).hexdigest()[:16])
 assets['microblocks.html']=html.encode()
 output.mkdir(parents=True,exist_ok=True)
 for name,raw in assets.items():target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 report=dict(real_editor='MicroBlocks GP 2.5.8',files=len(assets),p4_library_sha256=hashlib.sha256((repo/'boards/waveshare_esp32p4_wifi6/integration/P4_Camera.ubl').read_bytes()).hexdigest(),gp_data_sha256=hashlib.sha256(data).hexdigest(),runtime_external_network=False)
 (output/'p4-editor-manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--ide-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(build(a.ide_source,a.output,Path(__file__).resolve().parents[1]),indent=2))
