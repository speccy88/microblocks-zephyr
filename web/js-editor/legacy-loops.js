// SPDX-License-Identifier: MPL-2.0
// Preserve imported GP while loops using the stock repeat-until bytecode shape.
(function(root){
 'use strict';const installed=new WeakSet();
 function install(Compiler){
  if(installed.has(Compiler))return;const emit=Compiler.prototype.emitCmd;
  for(const name of ['emitCmd','instructionsForExpression','instructionsForCmdList','instructionsForJump','fixLoopExits'])if(typeof Compiler.prototype[name]!=='function')throw Error('Pinned legacy-loop compiler hooks changed.');
  Compiler.prototype.emitCmd=function(cmd){
   if(cmd?.selector!=='while')return emit.call(this,cmd);
   const inputs=cmd.argInputs();if(inputs.length!==2)throw Error('Invalid imported while loop.');
   const condition=[...this.instructionsForExpression(this.exprArg(inputs,0)),['not',1]];
   const body=this.instructionsForCmdList(this.cmdListArg(inputs,1));
   const result=[...this.instructionsForJump('jmp',body.length),...body,...condition,
    ...this.instructionsForJump('jmpFalse',-(body.length+condition.length+1))];
   this.fixLoopExits(result);return result;
  };installed.add(Compiler);
 }
 const api=Object.freeze({install});root.MicroBlocksLegacyLoops=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
