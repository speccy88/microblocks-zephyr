// SPDX-License-Identifier: MPL-2.0
// Persist implementation-only palette visibility using ordinary GP tag metadata.
(function(root) {
    'use strict';
    const marker='_microblocks_hidden_implementation',installed=new WeakSet();
    function install(Module) {
        if(installed.has(Module))return;
        const proto=Module?.prototype,save=proto?.codeString,load=proto?.loadFromCmds;
        if(typeof save!=='function'||typeof load!=='function')throw Error('Review library visibility hooks');
        proto.codeString=function(...args) {
            const text=save.apply(this,args);
            if(!this.isImplementation)return text;
            const newline=text.indexOf('\n');
            if(newline<0)throw Error('Review library module declaration');
            return text.slice(0,newline+1)+"tags '"+marker+"'\n"+text.slice(newline+1);
        };
        proto.loadFromCmds=function(...args) {
            const result=load.apply(this,args);
            if(this.tags.includes(marker)) {
                this.beImplementation();
                this.tags=this.tags.filter(tag=>tag!==marker);
            }
            return result;
        };
        installed.add(Module);
    }
    root.MicroBlocksLibraryVisibility=Object.freeze({install});
    if(typeof MB_Module==='function')install(MB_Module);
})(globalThis);
