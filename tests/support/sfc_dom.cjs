/* SPDX-License-Identifier: MIT - synthetic DOM; no browser or device. */
const assert=require('node:assert/strict');const fs=require('node:fs');const C=require('../../web/sfc/sfc-core.js');const UI=require('../../web/sfc/sfc-studio.js');
class Element{
 constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attributes={};this.dataset={};this.value='';this._text='';this.hidden=false;this.className='';this.classList={add:n=>this.className+=' '+n};}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
 append(...nodes){for(const n of nodes){n.parentNode=this;this.children.push(n);if(this.tagName==='SELECT'&&this.children.length===1)this.value=n.value;}}
 prepend(...nodes){for(const n of nodes.reverse()){n.parentNode=this;this.children.unshift(n);}}
 replaceChildren(...nodes){this._text='';this.children=[];this.append(...nodes);}
 setAttribute(name,value){this.attributes[name]=String(value);if(name.startsWith('data-'))this.dataset[name.slice(5)]=String(value);}
 getAttribute(name){return this.attributes[name]??null;}
 find(fn){if(fn(this))return this;for(const n of this.children){const result=n.find(fn);if(result)return result;}}
 showModal(){this.open=true;}
 close(){this.open=false;this.onclose?.({});}
 createSVGPoint(){return {x:0,y:0,matrixTransform(){return {x:this.x,y:this.y};}};}
 getScreenCTM(){return {inverse:()=>({})};}
 setPointerCapture(){}
}
function harness({saved,confirm=true,failSave=false,onOpenProgram=null,entries={}}={}){
 const document={body:new Element('body'),createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
 const writes=[],writeKeys=[],values=new Map(Object.entries(entries));if(saved!==undefined)values.set(UI.PLAN_STORAGE,saved);
 const storage={getItem:key=>values.get(key)??null,setItem:(key,value)=>{if(failSave)throw Error('Quota');values.set(key,value);writes.push(value);writeKeys.push(key);}};
 const library=fs.readFileSync(require('node:path').join(__dirname,'../../integration/Steps_Transitions.ubl'),'utf8');
 const studio=UI.mount({document,storage,library,confirm:()=>confirm,onOpenProgram});studio.open();
 const find=fn=>{const n=document.body.find(fn);assert(n,'Missing UI element');return n;};
 const text=(value,tag='BUTTON')=>find(n=>n.tagName===tag&&n.textContent===value);
 const aria=value=>find(n=>n.attributes['aria-label']===value);
 const click=node=>{assert(!node.disabled,'Disabled control '+node.textContent);return node.onclick?.({target:node,stopPropagation(){},preventDefault(){}});};
 const change=(node,value)=>{assert(!node.disabled);if(node.type==='checkbox')node.checked=value;else node.value=String(value);node.onchange?.();};
 const graph=()=>{click(text('Chart JSON'));return C.parse(aria('Chart JSON source').value);};
 return {document,studio,writes,writeKeys,values,text,aria,click,change,graph,find};
}
module.exports={Element,harness};
