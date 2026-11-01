/* SPDX-License-Identifier: MIT
 * Independent test interpreter for emitted control/Boolean syntax, NOT GP VM. */
'use strict';
function parse(source){
 const text=source.split("\nmodule 'Steps & Transitions'")[0],tokens=[];
 const re=/\r?\n|[ \t]+|'[^'\r\n]*'|[A-Za-z_][A-Za-z_0-9]*|-?\d+|[{}()=]/gy;
 let pos=0;while(pos<text.length){re.lastIndex=pos;const m=re.exec(text);if(!m)throw Error('Unsupported GP subset token at '+pos);pos=re.lastIndex;if(!/^[ \t]+$/.test(m[0]))tokens.push(m[0]);}
 let i=0;const functions=new Map(),scripts=[],variables=[];
 const take=()=>tokens[i++],peek=()=>tokens[i],expect=t=>{if(take()!==t)throw Error('Expected '+t);},lines=()=>{while(peek()==='\n')take();};
 function expression(){
  const t=take();if(t==='('){const name=take().replace(/^'|'$/g,''),args=[];while(peek()!==')'){if(i>=tokens.length||peek()==='\n')throw Error('Unclosed expression');args.push(expression());}expect(')');return {call:name,args};}
  if(t==='true'||t==='false')return {literal:t==='true'};
  if(/^-?\d+$/.test(t||''))return {literal:Number(t)};
  if(/^[A-Za-z_][A-Za-z_0-9]*$/.test(t||''))return {variable:t};
  throw Error('Unsupported expression '+t);
 }
 function block(){
  expect('{');const body=[];lines();while(peek()!=='}'){
   if(i>=tokens.length)throw Error('Unclosed block');const name=take();
   if(name==='if'){const condition=expression();body.push({if:condition,body:block()});}
   else if(name==='forever')body.push({forever:block()});
   else if(name==='return')body.push({return:expression()});
   else if(peek()==='='){take();body.push({set:name,value:expression()});}
   else{const args=[];while(!['\n','}'].includes(peek())){if(i>=tokens.length)throw Error('Unclosed command');args.push(expression());}body.push({call:name,args});}
   lines();
  }expect('}');return body;
 }
 while(i<tokens.length){lines();if(i>=tokens.length)break;const head=take();
  if(head==='to'){const name=take();if(functions.has(name))throw Error('Duplicate function');functions.set(name,block());}
  else if(head==='script'){take();take();scripts.push(block());}
  else if(['module','description','variables'].includes(head)){while(i<tokens.length&&peek()!=='\n'){const t=take();if(head==='variables')variables.push(t);}}
  else throw Error('Unsupported top-level '+head);
 }
 return {functions,scripts,variables};
}
class Interpreter{
 constructor(source,native){this.project=parse(source);this.vars=Object.fromEntries(this.project.variables.map(v=>[v,false]));this.native=native;this.budget=100000;}
 expression(e){if(Object.hasOwn(e,'literal'))return e.literal;if(e.variable){if(!Object.hasOwn(this.vars,e.variable))throw Error('Undefined '+e.variable);return this.vars[e.variable];}return this.call(e.call,e.args.map(x=>this.expression(x)));}
 call(name,args=[]){
  if(--this.budget<0)throw Error('Test execution budget exceeded');
  if(name==='not')return !args[0];if(name==='or')return args[0]||args[1];
  if(this.project.functions.has(name)){const returned=this.block(this.project.functions.get(name));return returned?.value;}
  if(name==='stepsStop')return this.native('[steps:stop]',[]);
  if(name.startsWith('[steps:'))return this.native(name,args);
  throw Error('Unsupported test call '+name);
 }
 block(body){for(const s of body){if(Object.hasOwn(s,'return'))return {value:this.expression(s.return)};
   if(s.set){if(!Object.hasOwn(this.vars,s.set))throw Error('Undeclared variable '+s.set);this.vars[s.set]=this.expression(s.value);}
   else if(s.if){if(this.expression(s.if)){const r=this.block(s.body);if(r)return r;}}
   else if(s.forever)throw Error('Real-time scheduler intentionally not executed by subset test');
   else this.call(s.call,s.args.map(x=>this.expression(x)));
  }return null;}
}
module.exports={parse,Interpreter};
