// SPDX-License-Identifier: MIT
// Execute the actual queue with simulated asynchronous DOM resource events.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[2],'utf8');
async function run(failAt=0,foreign=false){
 let active=0,peak=0,requests=[],inline=[],notice={textContent:''},listeners={};
 const root={dataset:{}};let context;
 const start=(node,url)=>{
  requests.push(url);active++;peak=Math.max(peak,active);
  setTimeout(()=>{
   active--;
   if(failAt&&requests.length===failAt)node.onerror();
   else{
    if(url==='emModule.js')context.Module={};
    if(url==='ide.js')context.IDE={init(){context.initialized=true;}};
    node.onload();
    if(url.startsWith('gp_wasm.js'))setTimeout(()=>document.dispatchEvent(new Event('ready')),1);
   }
  },1);
 };
 const resource=()=>{
  const node={dataset:{},tag:'resource'};
  Object.defineProperty(node,'href',{set(url){start(node,url);}});
  Object.defineProperty(node,'src',{set(url){start(node,url);}});
  return node;
 };
 const styles=[resource(),resource()],images=[resource(),resource()];
 styles.forEach((n,i)=>n.dataset.fjHref=foreign?'http://untrusted.invalid/style.css':'styles/'+i+'.css');
 images.forEach((n,i)=>n.dataset.fjSrc='img/'+i+'.svg');
 const document={documentElement:root,readyState:'complete',
  addEventListener(name,callback){(listeners[name]??=[]).push(callback);},
  dispatchEvent(event){for(const callback of listeners[event.type]||[])callback(event);},
  querySelectorAll(selector){return selector.startsWith('link')?styles:images;},
  querySelector(){return notice;},
  createElement(){return {tag:'script'};},
  head:{appendChild(node){
   if(node.src)start(node,node.src);
   else{inline.push(requests.length);vm.runInContext(node.textContent,context);}
  }}
 };
 context=vm.createContext({document,window:{addEventListener(){throw Error('Unexpected readiness wait');}},
  location:{href:'http://192.168.1.7/',origin:'http://192.168.1.7'},URL,Event,setTimeout,clearTimeout,
  console:{error(){}},initialized:false});
 vm.runInContext(source,context);
 const deadline=Date.now()+1500;
 while(Date.now()<deadline&&!['ready','failed'].includes(root.dataset.fjBootstrap))await new Promise(r=>setTimeout(r,2));
 return {state:root.dataset.fjBootstrap,active,peak,requests,inline,initialized:context.initialized,notice:notice.textContent};
}
(async()=>{
 const normal=await run();assert.equal(normal.state,'ready');assert.equal(normal.peak,1);assert.equal(normal.active,0);assert(normal.initialized);
 const js=normal.requests.filter(x=>x.endsWith('.js')||x.startsWith('gp_wasm.js'));
 assert.deepEqual(js,['emModule.js','gpSupport.js','FileSaver.js','ide.js','menus.js','buttons.js','categories.js','unoq-network.js','devtools.js','gettext.js','windows.js','graph.js','lib/usbDfuDevice.js','gp_wasm.js?v=26eb855451371f4c']);
 assert.equal(normal.inline.length,2);
 const failed=await run(6);assert.equal(failed.state,'failed');assert.equal(failed.requests.length,6);assert.equal(failed.peak,1);assert(failed.notice.includes('Reload'));
 const external=await run(0,true);assert.equal(external.state,'failed');assert.equal(external.requests.length,0);
 console.log(JSON.stringify({result:'PASS',scope:'Actual native bootstrap queue with simulated asynchronous DOM events; real browser acceptance separate',max_simultaneous_resources:normal.peak,external_scripts:js.length,inline_scripts:normal.inline.length,error_stops_queue:true,foreign_startup_rejected:true}));
})().catch(e=>{console.error(e);process.exitCode=1;});
