/* SPDX-License-Identifier: MIT — optional, disconnected chart authoring UI. */
(function(root,factory){
 'use strict';
 if(typeof module==='object'&&module.exports)module.exports=factory(require('./sfc-core.js'),require('./sfc-execution.js'),require('./sfc-export.js'));
 else{
  const api=factory(root.MicroBlocksSFC,root.MicroBlocksSFCExecution,root.MicroBlocksSFCExport);root.MicroBlocksSFCStudio=api;
  document.addEventListener('board-ide-ready',()=>setTimeout(()=>{
   const panel=document.querySelector('[data-device-project-panel]');
   if(!panel||document.getElementById('sfc-studio'))return;
   let storage;try{storage=root.localStorage;}catch{}
   const studio=api.mount({document,storage,library:root.MicroBlocksSFCLibrary,
    confirm:message=>root.confirm(message),onOpenProgram:async(name,source)=>{
     if(root.PORTAL_BOARD?.connection_enabled!==false)throw Error('Use the disconnected SFC editor package to import this draft.');
     const editor=new root.MicroBlocksPortal.EditorAPI(root.GP,document);
     return editor.call('portal.load',[name,source]);
    }});
   const entry=document.createElement('button');entry.textContent='Steps & transitions chart';entry.type='button';entry.onclick=()=>studio.open();panel.prepend(entry);
  },0));
 }
})(typeof globalThis==='object'?globalThis:this,function(C,E,X){
 'use strict';
 const STORAGE='microblocks-sfc-chart-v1';
 const PLAN_STORAGE='microblocks-sfc-plan-v1';
 const NS='http://www.w3.org/2000/svg';
 function mount({document,storage,library='',confirm=()=>false,onOpenProgram=null,parent=document.body}){
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
  const svg=(tag,attrs={})=>{const node=document.createElementNS(NS,tag);for(const [name,value] of Object.entries(attrs))node.setAttribute(name,String(value));return node;};
  const button=(label,fn)=>{const node=el('button',label);node.type='button';node.onclick=fn;return node;};
  let initial=E.fromGraph(C.example()),loadWarning='';
  try{const saved=storage?.getItem(PLAN_STORAGE);if(saved)initial=E.parseDraft(saved);else{const legacy=storage?.getItem(STORAGE);if(legacy)initial=E.fromGraph(C.parse(legacy));}}catch{loadWarning='Saved chart could not be read. It has not been overwritten.';}
  const history=new E.DraftHistory(initial);let selected=null,pin=null,runtime=null,inputs={},drag=null,busy=false;
  const plan=()=>history.present,graph=()=>plan().graph,running=()=>!!runtime?.state().running;
  const dialog=el('dialog',undefined,'sfc-studio');dialog.id='sfc-studio';dialog.setAttribute('aria-labelledby','sfc-title');parent.append(dialog);
  const header=el('header',undefined,'sfc-header'),title=el('h2','Steps & transitions');title.id='sfc-title';
  const chartName=el('input');chartName.type='text';chartName.maxLength=80;chartName.setAttribute('aria-label','Chart name');chartName.onchange=()=>attempt(()=>{const next=C.copy(graph());next.name=chartName.value;edit(C.checked(next));});
  const close=button('Close',()=>dialog.close());header.append(title,chartName,el('span','Local preview · no board connection','sfc-badge'),close);dialog.append(header);
  const toolbar=el('div',undefined,'sfc-toolbar');dialog.append(toolbar);
  const locked=[];
  const editButton=(label,fn)=>{const b=button(label,()=>attempt(fn));locked.push(b);toolbar.append(b);return b;};
  const addStep=editButton('+ Step',()=>add('step')),addTransition=editButton('+ Transition',()=>add('transition'));
  const undo=editButton('Undo',()=>{history.undo();selected=pin=null;changed();}),redo=editButton('Redo',()=>{history.redo();selected=pin=null;changed();});
  editButton('New chart',()=>{if(confirm('Replace this chart draft? The MicroBlocks project is unchanged.'))commit(C.empty());});
  const examples=el('select');examples.setAttribute('aria-label','Chart example');
  for(const [value,label] of [['','Examples…'],['sequence','Sequence + return'],['parallel','AND fork + join'],['selection','OR selection']]){const option=el('option',label);option.value=value;examples.append(option);}
  examples.onchange=()=>attempt(()=>{if(examples.value&&confirm('Replace this chart draft with an example?'))commit(C.example(examples.value));examples.value='';});toolbar.append(examples);locked.push(examples);
  const jsonButton=button('Chart JSON',()=>{jsonArea.value=C.serialize(graph());jsonPane.hidden=!jsonPane.hidden;projectPane.hidden=true;});toolbar.append(jsonButton);
  const planButton=button('Execution JSON',()=>{planArea.value=E.serializeDraft(plan());planPane.hidden=!planPane.hidden;jsonPane.hidden=projectPane.hidden=true;});toolbar.append(planButton);
  const exportButton=button('MicroBlocks blocks',()=>attempt(()=>{programArea.value=X.program(plan(),library);projectPane.hidden=false;jsonPane.hidden=planPane.hidden=true;}));toolbar.append(exportButton);
  const layout=el('div',undefined,'sfc-layout'),workspace=el('section',undefined,'sfc-workspace'),aside=el('aside',undefined,'sfc-inspector');layout.append(workspace,aside);dialog.append(layout);
  const chart=svg('svg',{'aria-label':'Steps chart',role:'group',tabindex:'0'});chart.classList.add('sfc-canvas');workspace.append(chart);
  let zoom=1;const viewTools=el('div',undefined,'sfc-view-tools'),zoomLabel=el('span','Fit');
  function setZoom(value){zoom=Math.max(1,Math.min(4,value));chart.setAttribute('style','width:'+zoom*100+'%;height:'+zoom*100+'%');zoomLabel.textContent=zoom===1?'Fit':Math.round(zoom*100)+'%';}
  const zoomIn=button('+',()=>setZoom(zoom+.25)),zoomOut=button('−',()=>setZoom(zoom-.25)),fit=button('Fit',()=>setZoom(1));zoomIn.setAttribute('aria-label','Zoom chart in');zoomOut.setAttribute('aria-label','Zoom chart out');viewTools.append(zoomOut,zoomLabel,zoomIn,fit);workspace.append(viewTools);
  const selection=el('section'),validation=el('section',undefined,'sfc-validation');aside.append(selection,validation);
  const signalsPanel=el('section',undefined,'sfc-signals');aside.append(signalsPanel);
  const preview=el('section',undefined,'sfc-preview');aside.append(preview);preview.append(el('h3','Logical preview'));
  const previewButtons=el('div',undefined,'sfc-preview-buttons'),start=button('Start preview',()=>attempt(()=>{runtime=new E.Execution(plan());runtime.start();inputs={};render();message('Initial step activated in this browser.');}));
  const advance=el('input');advance.type='number';advance.min='0';advance.max='86400000';advance.step='1';advance.value='100';advance.setAttribute('aria-label','Advance preview by milliseconds');
  const scan=button('One scan',()=>attempt(()=>{const ms=Number(advance.value);if(!Number.isSafeInteger(ms)||ms<0||ms>C.LIMITS.delay)throw Error('Enter an integer advance from 0 to 86400000 ms.');runtime.scan(runtime.state().now+ms,inputs);render();message('Scanned current steps once.');}));
  const stop=button('Stop / reset',()=>{runtime?.stopAndClear();pin=null;render();message('Preview reset. Every step is inactive.');});
  previewButtons.append(start,scan,stop);preview.append(previewButtons,el('label','Advance per scan (ms)'),advance);
  const restartTarget=el('select');restartTarget.setAttribute('aria-label','Preview restart step');
  const restart=button('Restart at step',()=>attempt(()=>{runtime.restartAt(Number(restartTarget.value));render();message('Preview restarted at the selected step.');}));
  const resetInitial=button('Reset to initial',()=>attempt(()=>{runtime.resetInitial();render();message('Preview restarted at its configured initial step.');}));
  preview.append(restartTarget,restart,resetInitial,el('p','Restart at step is preview-only. Export reset returns to the initial step.'));
  const conditions=el('div',undefined,'sfc-conditions'),state=el('p',undefined,'sfc-state');state.setAttribute('role','status');preview.append(conditions,state);
  const actionState=el('div',undefined,'sfc-action-state');actionState.setAttribute('aria-label','Logical action requests');preview.append(actionState);
  const note=el('p','OR follows configured priority. AND needs every preceding step. Action requests do not control devices.','sfc-note');aside.append(note);
  const jsonPane=el('section',undefined,'sfc-source-pane');jsonPane.hidden=true;dialog.append(jsonPane);
  const jsonArea=el('textarea');jsonArea.rows=6;jsonArea.spellcheck=false;jsonArea.setAttribute('aria-label','Chart JSON source');
  const loadJSON=button('Load JSON',()=>attempt(()=>{ensureStopped();const imported=C.parse(jsonArea.value);if((plan().bindings.length||plan().signals.length||plan().priority)&&!confirm('Graph-only JSON clears actions and priorities. Keep an Execution JSON copy first. Continue?'))return;commit(imported);jsonPane.hidden=true;message('Chart draft loaded.');}));jsonPane.append(el('h3','Graph source'),el('p','Graph only: actions and priorities are in Execution JSON.'),jsonArea,loadJSON);
  const planPane=el('section',undefined,'sfc-source-pane');planPane.hidden=true;dialog.append(planPane);
  const planArea=el('textarea');planArea.rows=6;planArea.spellcheck=false;planArea.setAttribute('aria-label','Execution JSON source');
  const loadPlan=button('Load execution JSON',()=>attempt(()=>{ensureStopped();const imported=E.parseDraft(planArea.value);history.commit(imported);selected=null;changed();planPane.hidden=true;message('Execution draft loaded.');}));planPane.append(el('h3','Execution source - graph, actions and priority'),planArea,loadPlan);
  const projectPane=el('section',undefined,'sfc-source-pane');projectPane.hidden=true;dialog.append(projectPane);
  const programArea=el('textarea');programArea.rows=6;programArea.readOnly=true;programArea.spellcheck=false;programArea.setAttribute('aria-label','Generated MicroBlocks project');
  const openProgram=button('Open in MicroBlocks',async()=>{
   if(!onOpenProgram||busy)return;
   if(!confirm('Replace the open MicroBlocks project with this logical chart? Save your current project first.'))return;
   busy=true;controls();
   try{await onOpenProgram(graph().name,X.program(plan(),library));dialog.close();message('Project sent to the disconnected MicroBlocks editor.');}
   catch(error){message(error.message,true);}finally{busy=false;controls();}
  });projectPane.append(el('h3','MicroBlocks project · one-way export'),el('p','Boolean sfc_t variables are transition inputs. The exported script scans every 50 ms; this preview advances only when you click One scan.'),programArea,openProgram);
  const footer=el('footer',undefined,'sfc-footer'),status=el('p'),draft=el('span');status.setAttribute('role','status');status.setAttribute('aria-live','polite');footer.append(status,draft);dialog.append(footer);
  function message(text,error=false){status.textContent=text;status.dataset.error=String(error);}
  function attempt(fn){try{if(!busy)fn();}catch(error){message(error.message,true);}}
  function ensureStopped(){if(running())throw Error('Stop/reset the preview before editing the chart.');}
  function persist(){try{if(storage){storage.setItem(PLAN_STORAGE,E.serializeDraft(plan()));draft.textContent='Execution draft saved in this browser';}else draft.textContent='Keep an Execution JSON copy';}catch{draft.textContent='Browser save failed - keep a JSON copy';}}
  function changed(){runtime=null;pin=null;projectPane.hidden=true;persist();render();}
  function commit(next){ensureStopped();history.commit(E.fromGraph(next));selected=null;changed();}
  function edit(next){ensureStopped();history.commit(E.withGraph(plan(),next));changed();}
  function editPlan(next){ensureStopped();history.commit(E.checked(next,{complete:false}));changed();}
  function add(kind){
   ensureStopped();const old=selected?.node?C.nodeAt(graph(),selected.node):null;
   const x=old?.x||360,y=Math.min(2100,old?old.y+150:80);
   const added=C.add(graph(),kind,{x,y});let next=added.graph;
   if(old&&old.kind!==kind)next=C.connect(next,C.key(old),added.id);
   edit(next);selected={node:added.id};render();message('Added '+added.id.toUpperCase()+(old&&old.kind!==kind?' and connected it.':'.'));
  }
  function clickPin(id,side){
   attempt(()=>{ensureStopped();if(!pin){pin={id,side};message('Choose the opposite pin of a '+(id[0]==='s'?'transition':'step')+'.');draw();return;}
    const next=C.connectPins(graph(),pin,{id,side});edit(next);message('Connection added.');});
  }
  function controls(){
   let valid=false;try{E.checked(plan());valid=true;}catch{}
   for(const node of locked)node.disabled=running()||busy;
   chartName.disabled=running()||busy;
   undo.disabled=running()||busy||!history.past.length;redo.disabled=running()||busy||!history.future.length;
   start.disabled=running()||!valid||busy;scan.disabled=!running()||busy;stop.disabled=!runtime||busy;
   loadPlan.disabled=running()||busy;restart.disabled=!runtime||busy;resetInitial.disabled=!runtime||busy;restartTarget.disabled=!runtime||busy;
   exportButton.disabled=!valid||busy;loadJSON.disabled=running()||busy;openProgram.disabled=!onOpenProgram||busy||!valid;
  }
  function field(label,input,fn){const wrap=el('label',label);input.setAttribute('aria-label',label);input.disabled=running();input.onchange=()=>attempt(fn);wrap.append(input);selection.append(wrap);return input;}
  function inspector(){
   selection.replaceChildren();validation.replaceChildren(el('h3','Chart check'));
   const problems=C.validate(graph());
   for(const problem of problems)validation.append(el('p',problem.message));if(!problems.length)validation.append(el('p','Ready for preview and export.'));
   if(selected?.node){
    const n=C.nodeAt(graph(),selected.node);selection.append(el('h3',C.key(n).toUpperCase()+' · '+n.kind));
    const label=el('input');label.value=n.label;label.maxLength=48;
    field('Element label',label,()=>edit(C.update(graph(),C.key(n),{label:label.value})));
    if(n.kind==='step'){
     const initial=el('input');initial.type='checkbox';initial.checked=n.initial;
     field('Initial step',initial,()=>edit(initial.checked?C.initial(graph(),C.key(n)):C.update(graph(),C.key(n),{initial:false})));
     const signal=el('select');signal.setAttribute('aria-label','Action signal');for(const s of plan().signals){const option=el('option','A'+s.id+' '+s.label);option.value=String(s.id);signal.append(option);}signal.disabled=running()||!plan().signals.length;
     const qualifier=el('select');qualifier.setAttribute('aria-label','Action qualifier');for(const q of E.QUALIFIERS){const option=el('option',q);option.value=q;qualifier.append(option);}qualifier.disabled=running();
     const addAction=button('Add action',()=>attempt(()=>{const next=C.copy(plan());next.bindings.push({step:n.id,signal:Number(signal.value),qualifier:qualifier.value});editPlan(next);}));addAction.disabled=running()||!plan().signals.length;selection.append(el('h3','Step actions'),signal,qualifier,addAction);
     for(const b of plan().bindings.filter(b=>b.step===n.id)){const row=el('div','A'+b.signal+' '+b.qualifier+' '),remove=button('Remove action A'+b.signal+' '+b.qualifier,()=>attempt(()=>{const next=C.copy(plan());next.bindings=next.bindings.filter(x=>!(x.step===b.step&&x.signal===b.signal&&x.qualifier===b.qualifier));editPlan(next);}));remove.disabled=running();row.append(remove);selection.append(row);}
    }else{
     const guard=el('select');for(const [value,label] of [['input','Boolean input'],['always','Always true'],['never','Always false']]){const option=el('option',label);option.value=value;guard.append(option);}guard.value=n.guard;
     field('Transition condition',guard,()=>edit(C.update(graph(),C.key(n),{guard:guard.value})));
     const delay=el('input');delay.type='number';delay.min='0';delay.max=String(C.LIMITS.delay);delay.value=String(n.afterMs);
     field('Minimum source time (ms)',delay,()=>edit(C.update(graph(),C.key(n),{afterMs:Number(delay.value)})));
     const order=plan().priority||graph().nodes.filter(n=>n.kind==='transition').map(n=>n.id).sort((a,b)=>a-b),rank=order.indexOf(n.id);
     selection.append(el('p','Priority '+(rank+1)+': T'+n.id));
     for(const [label,delta] of [['Higher priority',-1],['Lower priority',1]]){const b=button(label,()=>attempt(()=>{const next=C.copy(plan());next.priority=order.slice();[next.priority[rank],next.priority[rank+delta]]=[next.priority[rank+delta],next.priority[rank]];editPlan(next);}));b.disabled=running()||rank+delta<0||rank+delta>=order.length;selection.append(b);}
    }
    const remove=button('Delete element',()=>attempt(()=>{const next=C.remove(graph(),C.key(n));selected=null;edit(next);}));remove.disabled=running();selection.append(remove);
   }else if(selected?.link){
    const l=selected.link;selection.append(el('h3','Connection'),el('p',l.from.toUpperCase()+' → '+l.to.toUpperCase()));
    const remove=button('Delete connection',()=>attempt(()=>{const next=C.disconnect(graph(),l.from,l.to);selected=null;edit(next);}));remove.disabled=running();selection.append(remove);
   }else selection.append(el('h3','Build your chart'),el('p','Select a step or transition to edit it. Add the next kind to connect it automatically, or click an output and an input pin.'));
  }
  function renderSignals(){
   signalsPanel.replaceChildren(el('h3','Logical signals'));
   const add=button('+ Signal',()=>attempt(()=>{const next=C.copy(plan());let id=1;while(next.signals.some(s=>s.id===id))id++;next.signals.push({id,label:'Signal '+id});editPlan(next);}));add.disabled=running()||plan().signals.length>=16;signalsPanel.append(add);
   for(const s of plan().signals){const row=el('div',undefined,'sfc-signal-row'),label=el('input');label.value=s.label;label.maxLength=48;label.setAttribute('aria-label','Signal A'+s.id+' label');label.disabled=running();label.onchange=()=>attempt(()=>{const next=C.copy(plan());next.signals.find(x=>x.id===s.id).label=label.value;editPlan(next);});
    const remove=button('Delete signal A'+s.id,()=>attempt(()=>{const next=C.copy(plan());next.signals=next.signals.filter(x=>x.id!==s.id);next.bindings=next.bindings.filter(x=>x.signal!==s.id);editPlan(next);}));remove.disabled=running();row.append(el('span','A'+s.id),label,remove);signalsPanel.append(row);
   }
  }
  function draw(){
   chart.replaceChildren();
   const defs=svg('defs'),marker=svg('marker',{id:'sfc-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});
   marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#536177'}));defs.append(marker);chart.append(defs);
   const nodes=graph().nodes,links=graph().links;
   const width=Math.max(760,...nodes.map(n=>n.x+120)),height=Math.max(540,...nodes.map(n=>n.y+100));chart.setAttribute('viewBox','0 0 '+width+' '+height);
   const branches=new Map();
   for(const n of nodes)for(const side of ['in','out']){
    const members=links.filter(l=>side==='in'?l.to===C.key(n):l.from===C.key(n));
    if(members.length<2)continue;
    const xs=[n.x,...members.map(l=>C.nodeAt(graph(),side==='in'?l.from:l.to).x)],y=n.y+(side==='in'?-76:76);
    branches.set(C.key(n)+side,{y,and:n.kind==='transition',min:Math.min(...xs),max:Math.max(...xs)});
   }
   for(const link of links){
    const a=C.nodeAt(graph(),link.from),b=C.nodeAt(graph(),link.to),sy=a.y+44,ty=b.y-44;
    let points;
    if(ty<=sy){const outside=Math.max(12,Math.min(a.x,b.x)-120);points=[[a.x,sy],[a.x,sy+24],[outside,sy+24],[outside,Math.max(12,ty-24)],[b.x,Math.max(12,ty-24)],[b.x,ty]];}
    else{const from=branches.get(link.from+'out'),to=branches.get(link.to+'in'),mid=from?.y??to?.y??Math.round((sy+ty)/2);points=[[a.x,sy],[a.x,mid],[b.x,mid]];if(to)points.push([b.x,to.y]);points.push([b.x,ty]);}
    const d=points.map((p,i)=>(i?'L':'M')+p.join(' ')).join(' ');
    const path=svg('path',{d,'marker-end':'url(#sfc-arrow)',class:'sfc-wire'+(selected?.link?.from===link.from&&selected?.link?.to===link.to?' selected':''),'aria-hidden':'true'});
    const hit=svg('path',{d,class:'sfc-wire-hit',role:'button',tabindex:0,'aria-label':'Connection '+link.from.toUpperCase()+' to '+link.to.toUpperCase()});
    hit.onclick=()=>{selected={link};pin=null;render();};hit.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();hit.onclick();}};chart.append(path,hit);
   }
   for(const branch of branches.values()){
    for(const offset of branch.and?[-3,3]:[0])chart.append(svg('line',{x1:branch.min-10,x2:branch.max+10,y1:branch.y+offset,y2:branch.y+offset,class:'sfc-branch'}));
    const label=svg('text',{x:branch.max+16,y:branch.y+4,class:'sfc-branch-label'});label.textContent=branch.and?'AND':'OR';chart.append(label);
   }
   for(const n of nodes){
    const id=C.key(n),active=n.kind==='step'&&!!(runtime?.state().active&C.bit(n.id));
    const group=svg('g',{transform:'translate('+n.x+' '+n.y+')',class:'sfc-node '+n.kind+(active?' active':'')+(selected?.node===id?' selected':''),role:'button',tabindex:0,'aria-label':(n.kind==='step'?'Step S':'Transition T')+n.id+' '+n.label+(active?' active':''),'aria-pressed':String(selected?.node===id)});
    if(n.kind==='step'){
     group.append(svg('rect',{x:-78,y:-31,width:156,height:62,rx:12,class:'sfc-step'}));
     if(n.initial)group.append(svg('rect',{x:-72,y:-25,width:144,height:50,rx:8,class:'sfc-initial'}));
    }else{group.append(svg('rect',{x:-83,y:-31,width:166,height:65,rx:8,class:'sfc-transition-hit'}),svg('rect',{x:-60,y:-1,width:120,height:7,rx:2,class:'sfc-transition-bar'}));}
    const identifier=svg('text',{x:n.kind==='step'?-62:-76,y:n.kind==='step'?-9:-16,class:'sfc-id'});identifier.textContent=id.toUpperCase();group.append(identifier);
    const label=svg('text',{x:0,y:n.kind==='step'?13:24,class:'sfc-label','text-anchor':'middle'});label.textContent=n.label.length>19?n.label.slice(0,18)+'…':n.label;group.append(label);
    if(active)group.append(svg('circle',{cx:63,cy:-14,r:5,class:'sfc-active-dot'}));
    group.onclick=()=>{selected={node:id};pin=null;render();};
    group.onkeydown=e=>{
     if(e.target!==group)return;if(e.key==='Enter'){e.preventDefault();group.onclick();}
     const moves={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]};
     if(moves[e.key]&&!running()){e.preventDefault();const [dx,dy]=moves[e.key];attempt(()=>edit(C.update(graph(),id,{x:Math.max(40,Math.min(2200,n.x+dx)),y:Math.max(40,Math.min(2200,n.y+dy))})));}
    };
    group.onpointerdown=e=>{
     if(running()||e.target?.dataset?.pin)return;
     const point=chart.createSVGPoint();point.x=e.clientX;point.y=e.clientY;const p=point.matrixTransform(chart.getScreenCTM().inverse());
     drag={id,element:group,x:n.x,y:n.y,startX:p.x,startY:p.y,lastX:n.x,lastY:n.y};chart.setPointerCapture?.(e.pointerId);e.preventDefault();
    };
    for(const side of ['in','out']){
     const port=svg('circle',{cx:0,cy:side==='in'?-44:44,r:8,class:'sfc-pin'+(pin?.id===id&&pin?.side===side?' pending':''),role:'button',tabindex:0,'aria-label':(side==='in'?'Input':'Output')+' pin '+id.toUpperCase(),'data-pin':side});
     port.onclick=e=>{e.stopPropagation();clickPin(id,side);};port.onpointerdown=e=>e.stopPropagation();port.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();clickPin(id,side);}};group.append(port);
    }
    chart.append(group);
   }
  }
  chart.onpointermove=e=>{
   if(!drag)return;const point=chart.createSVGPoint();point.x=e.clientX;point.y=e.clientY;const p=point.matrixTransform(chart.getScreenCTM().inverse());
   drag.lastX=Math.max(40,Math.min(2200,Math.round((drag.x+p.x-drag.startX)/10)*10));drag.lastY=Math.max(40,Math.min(2200,Math.round((drag.y+p.y-drag.startY)/10)*10));
   drag.element.setAttribute('transform','translate('+drag.lastX+' '+drag.lastY+')');
   // Commit only on release; a cancelled pointer cannot alter the saved chart.
   message('Move '+drag.id.toUpperCase()+' to '+drag.lastX+', '+drag.lastY+'; release to place.');
  };
  chart.onpointerup=()=>{if(!drag)return;const drop=drag;drag=null;attempt(()=>{edit(C.update(graph(),drop.id,{x:drop.lastX,y:drop.lastY}));selected={node:drop.id};render();});};
  chart.onpointercancel=()=>{drag=null;draw();message('Move cancelled; chart unchanged.');};
  chart.onkeydown=e=>{if(e.key==='Escape'){pin=null;draw();e.preventDefault();e.stopPropagation();}};
  function render(){
   chartName.value=graph().name;
   draw();inspector();renderSignals();conditions.replaceChildren();
   for(const node of graph().nodes.filter(n=>n.kind==='transition'&&n.guard==='input').sort((a,b)=>a.id-b.id)){
    const label=el('label','T'+node.id+' condition'),input=el('input');input.type='checkbox';input.checked=inputs[node.id]===true;input.setAttribute('aria-label','T'+node.id+' condition');input.onchange=()=>{inputs[node.id]=input.checked;};label.prepend(input);conditions.append(label);
   }
   const active=runtime?C.ids(runtime.state().active):[];
   state.textContent=(running()?'Running preview':'Preview stopped')+' · '+(runtime?.state().now||0)+' ms · active '+(active.length?active.map(id=>'S'+id).join(', '):'none');
   const previousTarget=restartTarget.value;restartTarget.replaceChildren();for(const n of graph().nodes.filter(n=>n.kind==='step')){const option=el('option','S'+n.id);option.value=String(n.id);restartTarget.append(option);}if(graph().nodes.some(n=>n.kind==='step'&&String(n.id)===previousTarget))restartTarget.value=previousTarget;
   actionState.replaceChildren();const a=runtime?.state().actions;for(const s of plan().signals){const value=!!(a?.requested&C.bit(s.id)),stored=!!(a?.stored&C.bit(s.id));actionState.append(el('p','A'+s.id+' '+s.label+' = '+value+(stored?' (stored)':'')));}
   controls();
  }
  dialog.onclose=()=>{runtime?.stopAndClear();pin=drag=null;};
  render();message(loadWarning||'Edit a chart, then start its local preview. No physical outputs are used.',!!loadWarning);
  return {dialog,open(){render();dialog.showModal();},close(){dialog.close();}};
 }
 return Object.freeze({mount,STORAGE,PLAN_STORAGE});
});
