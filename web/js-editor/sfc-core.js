// SPDX-License-Identifier: MPL-2.0
// Native SFC lowering, ported from this project's sfc-native/branches.gp.
// Plain syntax trees only. Execution remains ordinary SmallVM bytecode.
(function (root) {
    'use strict';
    const fail = message => { throw new Error('SFC: ' + message); };
    const node = (selector, args, isReporter = false) => ({selector, args, isReporter, next:null});
    const command = (op, ...args) => node(op, args);
    const reporter = (op, ...args) => node(op, args, true);
    const variable = name => reporter('v', name);
    const set = (name, value) => command('=', name, value);
    const copy = value => value == null || typeof value !== 'object' ? value :
        Array.isArray(value) ? value.map(copy) : Object.fromEntries(Object.entries(value).map(([k,v]) => [k,copy(v)]));
    const chain = (...commands) => {
        commands = commands.flat().filter(Boolean);
        for (let i=0;i<commands.length-1;i++) {
            let tail=commands[i];while(tail.next)tail=tail.next;
            tail.next=commands[i+1];
        }
        return commands[0] || null;
    };
    function walk(value, visit) {
        if (!value || typeof value !== 'object') return;
        if (Array.isArray(value)) { value.forEach(v=>walk(v,visit)); return; }
        if (typeof value.selector !== 'string' || !Array.isArray(value.args)) return;
        visit(value); value.args.forEach(v=>walk(v,visit)); walk(value.next,visit);
    }
    const truth = name => reporter('==', variable(name), true);
    const all = values => values.length ? values.slice(1).reduce((a,b)=>reporter('and',a,b),values[0]) : true;
    const bit = id => 1 << (id-1);
    const test = (mask,bits) => reporter('==',reporter('&',mask,bits),bits);
    const maskAdd = (name,bits) => set(name,reporter('|',variable(name),bits));
    const privateName = (prefix,field,id='') => prefix+field+id;
    const hasBranches = sequence => { let result=false; walk(sequence?.args?.[0],n=>{if(['sfcAnd','sfcOr'].includes(n.selector))result=true;}); return result; };
    const variableName = value => typeof value==='string' ? value : value?.selector==='v' && typeof value.args[0]==='string' ? value.args[0] : null;

    function graphFor(sequence, sharedNames, outerLocals = [], options = {}) {
        const shared=new Set(sharedNames), locals=new Set(outerLocals), branched=hasBranches(sequence);
        const graph={steps:[],edges:[],guards:[],initial:1,branched};
        function sharedVar(value) {
            const name=variableName(value);
            if (!name || !shared.has(name)) fail('create and select a shared step/transition variable first');
            if (locals.has(name)) fail('step/transition variables cannot be local variables or parameters');
            return name;
        }
        function actions(setup,loop) {
            const ownLocals=new Set();
            for(const body of [setup,loop]) walk(body,n=>{if(['local','for'].includes(n.selector))ownLocals.add(variableName(n.args[0]));});
            for(const body of [setup,loop]) walk(body,n=>{
                if(n.selector.startsWith('sfc'))fail('flow blocks cannot appear inside setup/loop actions');
                if(branched&&['return','stopTask','stopAll'].includes(n.selector))fail('actions cannot directly return or stop worker tasks');
                const name=n.selector==='v'?variableName(n):['=','+='].includes(n.selector)?variableName(n.args[0]):null;
                if(branched&&name && locals.has(name) && !ownLocals.has(name))fail('worker actions cannot capture enclosing local variables');
                if(options.knownSelector && !options.knownSelector(n.selector))fail('unknown operation inside an action: '+n.selector);
            });
        }
        function step(n) {
            if(!n || n.selector!=='sfcStep' || n.args.length!==3)fail('each path must begin and end with a step with setup and loop');
            const name=sharedVar(n.args[0]);
            if(graph.steps.some(s=>s.name===name))fail('duplicate step variable: '+name);
            if(branched && graph.steps.length>=8)fail('at most eight step workers per chart');
            actions(n.args[1],n.args[2]);
            const id=graph.steps.length+1;
            graph.steps.push({id,name,setup:copy(n.args[1]),loop:copy(n.args[2])}); return id;
        }
        function edge(from,to,guards) {
            if(graph.edges.length>=24)fail('at most 24 transition edges per chart');
            guards=guards.map(sharedVar);
            for(const guard of guards)if(!graph.guards.includes(guard))graph.guards.push(guard);
            if(graph.guards.length>24)fail('at most 24 shared guard variables per chart');
            graph.edges.push({from,to,guards});
        }
        function fork(source,n,common) {
            const parallel=n.selector==='sfcAnd', join=n.next;
            if(!join || join.selector!==(parallel?'sfcAndJoin':'sfcOrJoin') || join.args.length!==1)fail('split requires an immediately paired matching join/merge');
            const guard=sharedVar(join.args[0]), args=n.args, count=args.length/(parallel?1:2);
            if(!Number.isInteger(count)||count<2||count>6)fail('choose two through six branches');
            const entries=[];let finals=0;
            for(let i=0;i<count;i++) {
                const guards=parallel?common.slice():[...common,sharedVar(args[i*2])];
                const ends=path(args[i*(parallel?1:2)+(parallel?0:1)],true);
                entries.push({target:bit(ends.first),guards}); finals|=bit(ends.last);
            }
            const target=join.next, targetID=step(target);
            if(parallel) {
                if(!common.length)fail('AND split needs a preceding shared transition');
                edge(bit(source),entries.reduce((m,e)=>m|e.target,0),common);
                edge(finals,bit(targetID),[guard]);
            } else {
                for(const entry of entries)edge(bit(source),entry.target,entry.guards);
                for(const s of graph.steps)if(finals&bit(s.id))edge(bit(s.id),bit(targetID),[guard]);
            }
            return {id:targetID,node:target};
        }
        function path(n,branch) {
            const first=step(n);let current=first;
            while(n) {
                let next=n.next, common=[];
                if(!next) {if(!branch)fail('top-level terminal step needs a transition');return {first,last:current};}
                if(next.selector==='sfcTransition') {
                    if(next.args.length!==1)fail('transition needs one shared variable');
                    common.push(sharedVar(next.args[0])); next=next.next;
                    if(!next) {if(branch)fail('branch must finish on an active step before the join');edge(bit(current),0,common);return {first,last:current};}
                }
                if(next.selector==='sfcStep') {
                    if(!common.length)fail('adjacent steps need a transition');
                    const id=step(next);edge(bit(current),bit(id),common);current=id;n=next;
                } else if(['sfcAnd','sfcOr'].includes(next.selector)) {
                    const joined=fork(current,next,common);current=joined.id;n=joined.node;
                } else fail('ordinary commands belong inside setup/loop; invalid flow structure');
            }
            fail('empty path');
        }
        if(sequence?.selector!=='sfcSequence'||sequence.args.length!==1)fail('sequence needs one command section');
        path(sequence.args[0],false);
        for(const s of graph.steps)if(graph.guards.includes(s.name))fail('step and transition variables must be disjoint');
        return graph;
    }

    function serialBody(sequence,sharedNames,outerLocals=[]) {
        const graph=graphFor(sequence,sharedNames,outerLocals);
        if(graph.branched)fail('branch chart needs cooperative worker preparation');
        const commands=graph.steps.map(s=>set(s.name,false));
        for(let i=0;i<graph.steps.length;i++) {
            const s=graph.steps[i], guard=graph.edges[i].guards[0];
            commands.push(set(s.name,true),copy(s.setup));
            commands.push(s.loop ? command('repeatUntil',truth(guard),chain(command('if',true,copy(s.loop)),command('waitMillis',1))) : command('waitUntil',truth(guard)));
            commands.push(set(s.name,false));
        }
        return chain(commands);
    }

    function generate(graph,prefix) {
        const priv=(field,id='')=>privateName(prefix,field,id), v=field=>variable(priv(field));
        const terms=(field,mask=65535)=>graph.steps.filter(s=>mask&bit(s.id)).map(s=>truth(priv(field,s.id)));
        const publish=mask=>chain(graph.steps.map(s=>set(s.name,test(mask,bit(s.id)))));
        const elapsed=reporter('&',reporter('-',reporter('millisOp'),variable('_sfcTimer')),1073741823);
        const deadline=condition=>chain(command('local','_sfcTimer',reporter('millisOp')),
            command('repeatUntil',reporter('or',condition,reporter('>=',copy(elapsed),500)),command('waitMillis',1)));
        const functions=[];
        const fn=(name,args,body)=>functions.push({name:priv(name),args,body});
        for(const s of graph.steps) {
            const setup=priv('setup',s.id), request=priv('request',s.id);
            const actions=chain(command('if',reporter('not',truth(setup)),chain(command('repeat',1,copy(s.setup)),set(setup,true))),
                command('if',truth(request),set(priv('ack',s.id),true),true,command('repeat',1,copy(s.loop))));
            fn('worker'+s.id,[],chain(set(priv('ready',s.id),true),command('waitUntil',reporter('or',truth(priv('gate')),reporter('not',truth(priv('run'))))),
                command('repeatUntil',reporter('not',truth(priv('run'))),chain(command('if',test(v('active'),bit(s.id)),actions),command('waitMillis',1))),
                set(priv('done',s.id),true),command('stopTask')));
        }
        const init=[command('if',reporter('or',truth(priv('run')),reporter('==',v('status'),-2)),command('return',false)),set(priv('status'),1),set(priv('run'),true),set(priv('active'),0),set(priv('gate'),false)];
        for(const s of graph.steps) {
            init.push(set(s.name,false));
            for(const field of ['ready','setup','request','ack','done'])init.push(set(priv(field,s.id),false));
        }
        for(const s of graph.steps)init.push(command('sendBroadcast',priv('worker',s.id)));
        const ready=all(terms('ready'));
        init.push(command('repeat',1,deadline(copy(ready))),command('if',reporter('not',copy(ready)),chain(set(priv('run'),false),set(priv('gate'),true),set(priv('status'),-1),command('return',false))),command('return',true));
        fn('init',['dummy'],chain(init));
        const done=all(graph.steps.map(s=>reporter('or',reporter('not',truth(priv('ready',s.id))),truth(priv('done',s.id)))));
        fn('finish',['dummy'],chain(set(priv('run'),false),set(priv('gate'),true),command('repeat',1,publish(0)),set(priv('active'),0),command('repeat',1,deadline(copy(done))),
            command('if',reporter('not',copy(done)),chain(set(priv('status'),-2),command('return',false))),command('waitMillis',1),
            command('if',reporter('==',variable('dummy'),-3),set(priv('status'),-3)),command('return',true)));
        const inputBody=[command('local','_sfcInputs',0)];
        graph.guards.forEach((guard,i)=>inputBody.push(command('if',truth(guard),maskAdd('_sfcInputs',bit(i+1)))));
        inputBody.push(command('return',variable('_sfcInputs')));fn('inputs',['dummy'],chain(inputBody));
        const select=[command('local','_sfcUsed',0),command('local','_sfcTargets',0)];
        for(const e of graph.edges) {
            const conditions=terms('setup',e.from);
            conditions.push(test(variable('activeMask'),e.from),reporter('==',reporter('&',variable('_sfcUsed'),e.from),0),
                test(variable('inputMask'),e.guards.reduce((m,g)=>m|bit(graph.guards.indexOf(g)+1),0)));
            select.push(command('if',all(conditions),chain(maskAdd('_sfcUsed',e.from),maskAdd('_sfcTargets',e.to))));
        }
        select.push(command('return',reporter('|',variable('_sfcUsed'),reporter('<<',variable('_sfcTargets'),8))));fn('select',['activeMask','inputMask'],chain(select));
        const finish=reason=>command(priv('finish'),reason);
        const abort=reason=>chain(finish(reason),command('return',false));
        const owner=[command('if',reporter('not',reporter(priv('init'),0)),abort(0))];
        for(const name of ['_sfcActive','_sfcConsumed','_sfcActivated','_sfcInputs','_sfcSelected'])owner.push(command('local',name,0));
        owner.push(set('_sfcActive',graph.initial),command('repeat',1,publish(variable('_sfcActive'))),set(priv('active'),variable('_sfcActive')),set(priv('gate'),true),set(priv('status'),2));
        const scan=[set('_sfcInputs',reporter(priv('inputs'),0)),set('_sfcSelected',reporter(priv('select'),variable('_sfcActive'),variable('_sfcInputs'))),
            set('_sfcConsumed',reporter('&',variable('_sfcSelected'),255)),set('_sfcActivated',reporter('&',reporter('>>',variable('_sfcSelected'),8),255))];
        for(const s of graph.steps)scan.push(command('if',test(variable('_sfcConsumed'),bit(s.id)),set(priv('request',s.id),true)));
        const acks=all(graph.steps.map(s=>reporter('or',reporter('not',test(variable('_sfcConsumed'),bit(s.id))),truth(priv('ack',s.id)))));
        scan.push(command('waitUntil',reporter('or',acks,reporter('not',truth(priv('run'))))),command('if',reporter('not',truth(priv('run'))),abort(-3)),
            set('_sfcActive',reporter('|',reporter('&',variable('_sfcActive'),reporter('-',65535,variable('_sfcConsumed'))),variable('_sfcActivated'))),
            command('repeat',1,publish(variable('_sfcActive'))),set(priv('active'),variable('_sfcActive')),command('waitMillis',1));
        owner.push(command('repeatUntil',reporter('or',reporter('==',variable('_sfcActive'),0),reporter('not',truth(priv('run')))),chain(scan)),
            command('if',reporter('not',truth(priv('run'))),abort(-3)),command('if',reporter('not',reporter(priv('finish'),0)),command('return',false)),set(priv('status'),0),command('return',true));
        fn('owner',['dummy'],chain(owner));
        const variables=['run','gate','active','status'].map(f=>priv(f));
        for(const s of graph.steps)for(const f of ['ready','setup','request','ack','done'])variables.push(priv(f,s.id));
        return {functions,variables,invocation:command('if',reporter('not',reporter(priv('owner'),0)),command('return',false))};
    }
    const api=Object.freeze({graphFor,serialBody,generate,walk,copy,node,command,reporter,variable,chain,hasBranches,variableName});
    root.MicroBlocksSFCModel=api;
    if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
