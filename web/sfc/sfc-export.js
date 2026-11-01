/* SPDX-License-Identifier: MIT - logical requests only; one owning scan task. */
(function(root,factory){
 if(typeof module==='object'&&module.exports)module.exports=factory(require('./sfc-core.js'),require('./sfc-execution.js'));
 else root.MicroBlocksSFCExport=factory(root.MicroBlocksSFC,root.MicroBlocksSFCExecution);
})(typeof globalThis==='object'?globalThis:this,function(C,E){
 'use strict';
 function program(plan,library){
  E.checked(plan);if(typeof library!=='string'||!library.startsWith("module 'Steps & Transitions'"))throw new C.SFCError('LIBRARY','The existing Steps & Transitions library is required.');
  const compiled=E.compile(plan),cfg=C.compile(compiled.graph),signals=plan.signals.slice().sort((a,b)=>a.id-b.id),guards=C.compile(plan.graph).transitions.filter(t=>t.guard==='input');
  const vars=['sfc_ok',...guards.map(t=>'sfc_t'+t.id),...signals.flatMap(s=>['sfc_a'+s.id,'sfc_l'+s.id])];
  const lines=['module main','variables '+vars.join(' '),"description 'Logical SFC requests only. One owning scan task; stop it before manual setup/reset. Use sfcStopAndClear for request cleanup; red stop does not run this cleanup block. Native primitives and hardware compatibility require separate validation. Restart-at-step is preview-only.'",''];
  lines.push('to sfcClearRequests {');for(const s of signals)lines.push('    sfc_a'+s.id+' = false','    sfc_l'+s.id+' = false');lines.push('}','','to sfcPublishActions {');
  for(const s of signals)lines.push('    sfcPublishA'+s.id);lines.push('}');
  const join=items=>items.length===1?items[0]:'(or '+items[0]+' '+join(items.slice(1))+')';
  for(const s of signals){
   lines.push('','to sfcPublishA'+s.id+' {');
   for(const b of plan.bindings.filter(b=>b.signal===s.id&&b.qualifier==='S'))lines.push("    if ('[steps:entered]' "+b.step+') { sfc_l'+b.signal+' = true }');
   for(const b of plan.bindings.filter(b=>b.signal===s.id&&b.qualifier==='R'))lines.push("    if ('[steps:active]' "+b.step+') { sfc_l'+b.signal+' = false }');
   const terms=['sfc_l'+s.id];for(const b of plan.bindings.filter(b=>b.signal===s.id)){
    const flag={N:'active',P1:'entered',P0:'exited'}[b.qualifier];if(flag)terms.push("('[steps:"+flag+"]' "+b.step+')');
   }lines.push('    sfc_a'+s.id+' = '+join(terms),'}');
  }
  const definitions=[...cfg.steps.map(s=>"'[steps:add]' "+s.id+' '+s.initial),...cfg.transitions.map(t=>"'[steps:groups]' "+[t.id,t.from,t.to,t.afterMs].join(' '))],setup=[];
  const checked=call=>lines.push('    if (not ('+call+')) { return false }');
  for(let at=0;at<definitions.length;at+=8){const name='sfcDefine'+(setup.length+1);setup.push(name);lines.push('','to '+name+' {');for(const call of definitions.slice(at,at+8))checked(call);lines.push('    return true','}');}
  lines.push('','to sfcStopAndClear {','    sfc_ok = false','    sfcClearRequests','    stepsStop','}','','to sfcResetInitial {','    sfc_ok = false','    sfcClearRequests');
  checked("'[steps:stop]'");checked("'[steps:clear]'");for(const name of setup)checked(name);
  checked("'[steps:start]'");lines.push('    sfc_ok = true','    sfcPublishActions','    return true','}','','to sfcScan {','    if (not sfc_ok) { return false }');
  for(const t of cfg.transitions){const original=compiled.order[t.id-1],value=t.guard==='input'?'sfc_t'+original:t.guard==='always'?'true':'false';lines.push("    if (not ('[steps:condition]' "+t.id+' '+value+')) {','        sfcStopAndClear','        return false','    }');}
  lines.push("    if (not ('[steps:scan]')) {",'        sfcStopAndClear','        return false','    }','    sfcPublishActions','    return true','}','','script 30 30 {','    whenStarted','    sfc_ok = false','    sfcClearRequests');
  for(const t of guards)lines.push('    sfc_t'+t.id+' = false');
  lines.push('    sfcResetInitial','    forever {','        waitMillis 50','        sfcScan','    }','}','','script 450 30 {','    sfcStopAndClear','}','','script 450 140 {','    sfcResetInitial','}');
  return lines.join('\n')+'\n\n'+library;
 }
 return Object.freeze({program});
});
