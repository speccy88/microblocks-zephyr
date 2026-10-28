// SPDX-License-Identifier: MPL-2.0
// Restore exact local library specs before applying the board's function bodies.
(function(root){
 'use strict';const installed=new WeakMap(),MAX=262144;
 function validate(catalog){
  if(!catalog||catalog.schema!==1||!catalog.modules||Array.isArray(catalog.modules))throw Error('Invalid readback library catalog.');
  const entries=Object.entries(catalog.modules);if(entries.length>64)throw Error('Readback catalog is too large.');let total=0;
  for(const [name,entry] of entries){
   if(!name||name.length>128||['__proto__','constructor','prototype'].includes(name)||!entry||
    typeof entry.path!=='string'||!/^sources\/(target|microduck)\/[A-Za-z0-9_./ &()+-]+\.ubl$/.test(entry.path)||entry.path.split('/').some(x=>x==='.'||x==='..')||
    !Number.isInteger(entry.bytes)||entry.bytes<1||entry.bytes>MAX||!/^[a-f0-9]{64}$/.test(entry.sha256))throw Error('Invalid pinned readback source.');
   total+=entry.bytes;
  }if(total>2097152)throw Error('Readback catalog byte budget exceeded.');return catalog;
 }
 async function read(entry){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);let reader;
  try{
   const response=await root.fetch(entry.path,{redirect:'error',credentials:'same-origin',cache:'no-store',signal:controller.signal});
   if(!response.ok||!response.body)throw Error('Packaged readback source unavailable.');
   const length=response.headers?.get('content-length');if(length!==null&&length!==undefined&&(!/^\d+$/.test(length)||Number(length)!==entry.bytes))throw Error('Readback source length differs.');
   reader=response.body.getReader();const output=new Uint8Array(entry.bytes);let offset=0;
   for(;;){const part=await reader.read();if(part.done)break;if(!(part.value instanceof Uint8Array)||part.value.length>output.length-offset)throw Error('Readback source exceeds its pinned size.');output.set(part.value,offset);offset+=part.value.length;}
   if(offset!==output.length)throw Error('Truncated readback source.');return output;
  }finally{clearTimeout(timer);controller.abort();if(reader){try{await reader.cancel();}catch{}reader.releaseLock();}}
 }
 function install(Decompiler,catalog,{fetchBytes=read,crypto=root.crypto}={}){
  validate(catalog);if(typeof Decompiler?.prototype.addEmbeddedLibrary!=='function')throw Error('Pinned library readback hook changed.');
  const signature=JSON.stringify(catalog);if(installed.has(Decompiler)){if(installed.get(Decompiler)!==signature)throw Error('Cannot change pinned readback catalog.');return;}
  const original=Decompiler.prototype.addEmbeddedLibrary,addFunction=Decompiler.prototype.addFunctionToProject,cache=new Map(),privateNames=new WeakMap();
  async function source(entry){
   if(!cache.has(entry.path)){
    const pending=(async()=>{const bytes=await fetchBytes(entry);try{
     if(!(bytes instanceof Uint8Array)||bytes.length!==entry.bytes||!crypto?.subtle)throw Error('Readback source verification unavailable.');
     const hash=new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));if(Array.from(hash,b=>b.toString(16).padStart(2,'0')).join('')!==entry.sha256)throw Error('Pinned readback library hash differs.');
     return new TextDecoder('utf-8',{fatal:true}).decode(bytes);
    }finally{bytes?.fill?.(0);}})();
    cache.set(entry.path,pending);pending.catch(()=>{if(cache.get(entry.path)===pending)cache.delete(entry.path);});
   }return cache.get(entry.path);
  }
  Decompiler.prototype.addEmbeddedLibrary=async function(libName,project){
   const implementation=libName.startsWith('_'),name=implementation?libName.slice(1):libName;
   if(!Object.hasOwn(catalog.modules,name))return original.call(this,libName,project);
   const entry=catalog.modules[name],text=await source(entry);project.addLibraryFromString(text,name,'//'+entry.path);
   const lib=project.libraryNamed(name);if(!lib)throw Error('Pinned readback module name differs.');
   if(!privateNames.has(project))privateNames.set(project,new Map());
   privateNames.get(project).set(name,new Set(lib.functions.filter(f=>!project.blockSpecs.has(f.functionName)).map(f=>f.functionName)));
   if(implementation)lib.beImplementation();
   for(const dependency of lib.dependencies)if(!project.libraryNamed(dependency)&&!project.replacementFor(dependency))await this.addEmbeddedLibrary(dependency,project);
  };
  Decompiler.prototype.addFunctionToProject=async function(func,project){
   const module=(this.functionLibrary||'').replace(/^_/,''),info=this.functionSpecInfo||[];
   const generic=info[0]===' '&&info[1]===func.functionName+func.argNames.map(()=>' _').join('')&&info[2]===func.argNames.map(()=>'auto').join(' ');
   const result=await addFunction.call(this,func,project);
   if((!info[1]||generic)&&privateNames.get(project)?.get(module)?.has(func.functionName))project.blockSpecs.delete(func.functionName);
   return result;
  };
  installed.set(Decompiler,signature);
 }
 const api=Object.freeze({install,validate,read});root.MicroBlocksReadbackLibraries=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
