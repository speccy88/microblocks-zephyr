// SPDX-License-Identifier: MIT
// Register-fixture evaluator for production GP parse trees. This is not a VM
// or physical test. Unknown operations fail rather than silently succeeding.
'use strict';
class Returned { constructor(value){this.value=value;} }
const literal=s=>s.startsWith("'")&&s.endsWith("'")?s.slice(1,-1).replaceAll("''","'"):s;
function fixture(trees,{registers={},globals={},hooks={}}={}){
 const functions=new Map(trees.filter(t=>t[0]==='to').map(t=>[literal(t[1]),t]));
 let budget=100000;
 function value(node,scope){
  if(--budget<0)throw Error('Fixture operation budget exceeded');
  if(typeof node==='number'||typeof node==='boolean')return node;
  if(typeof node==='string'){
   if(node.startsWith("'"))return literal(node);
   if(node==='true')return true;if(node==='false')return false;
   return Object.hasOwn(scope,node)?scope[node]:(globals[node]??0);
  }
  const op=node[0],a=node.slice(1),v=n=>value(a[n],scope),name=n=>literal(a[n]);
  if(op==='local'){scope[name(0)]=v(1);return;}
  if(op==='='||op==='+='){
   const key=name(0),target=Object.hasOwn(scope,key)?scope:globals;
   target[key]=op==='='?v(1):(target[key]??0)+v(1);return;
  }
  if(op==='if'){
   for(let i=0;i<a.length;i+=2){if(a[i]==='else'){body(a[i+1],scope);break;}if(value(a[i],scope)){body(a[i+1],scope);break;}}
   return;
  }
  if(op==='return')throw new Returned(a.length?v(0):undefined);
  if(op==='comment')return;
  if(op==='hexToInt')return parseInt(v(0),16);
  if(op==='i2cGet')return registers[v(1)]??0;
  if(op==='[data:makeList]')return [];
  if(op==='[data:addLast]'){v(1).push(v(0));return;}
  if(op==='at'){const i=v(0),array=v(1);return array[i==='last'?array.length-1:i-1];}
  if(op==='atPut'){const i=v(0),array=v(1);if(!Array.isArray(array)||!Number.isInteger(i)||i<1||i>array.length)throw Error('Bad list store');array[i-1]=v(2);return;}
  const binary={'+':(x,y)=>x+y,'-':(x,y)=>x-y,'*':(x,y)=>x*y,'/':(x,y)=>Math.trunc(x/y),
   '&':(x,y)=>x&y,'|':(x,y)=>x|y,'<<':(x,y)=>x<<y,'>>':(x,y)=>x>>y,
   '>':(x,y)=>x>y,'>=':(x,y)=>x>=y,'<':(x,y)=>x<y,'<=':(x,y)=>x<=y,'==':(x,y)=>x===y,'!=':(x,y)=>x!==y};
  if(binary[op])return binary[op](v(0),v(1));
  const args=a.map(x=>value(x,scope));
  if(hooks[op])return hooks[op](...args);
  if(functions.has(op))return call(op,...args);
  throw Error('Unsupported fixture operation '+op);
 }
 function body(commands,scope){for(const cmd of commands)value(cmd,scope);}
 function call(name,...args){
  const fn=functions.get(name);if(!fn)throw Error('Missing function '+name);
  const scope={};fn.slice(2,-1).forEach((key,i)=>scope[literal(key)]=args[i]);
  try{body(fn.at(-1),scope);}catch(result){if(result instanceof Returned)return result.value;throw result;}
 }
 return {call,globals};
}
module.exports={fixture};
