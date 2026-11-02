#!/usr/bin/env python3
"""Real GP bytecode + real SmallVM PTY, with unchanged C-engine stable-state oracle."""
# SPDX-License-Identifier: MPL-2.0
import argparse,hashlib,importlib.util,json,os,struct,tempfile,time,subprocess
from pathlib import Path


class COracle:
 def __init__(self,host,plan):
  self.host=host;self.plan=plan;self.values={};self.tick=0;self.lines=['INIT 0']
  n=len(plan['steps']);self.visible=(1<<n)-1;self.sink=1<<n
  for i,name in plan['steps']:self.lines.append(f'ADD {i} {int(bool(plan["initial"]&(1<<(i-1))))}')
  self.lines.append(f'ADD {n+1} 0')
  for i,(source,target,guards) in enumerate(plan['edges'],1):self.lines.append(f'EDGE {i} {source} {target or self.sink} 0')
  self.lines.append('START 0');self.states=[]
 def settle(self,values):
  self.values.update(values)
  for _ in range(len(self.plan['steps'])+2):
   self.tick+=1
   for i,(source,target,guards) in enumerate(self.plan['edges'],1):
    ready=all(self.values.get(name) is True for name in guards)
    self.lines.append(f'COND {i} {int(ready)}')
   self.lines.append(f'SCAN {self.tick}')
  p=subprocess.run([str(self.host)],input='\n'.join(self.lines)+'\n',text=True,capture_output=True,timeout=10,check=True)
  self.states=[json.loads(x) for x in p.stdout.splitlines()];assert all(s['error']==0 for s in self.states)
  return self.states[-1]['active']&self.visible


def run(binary,host,reports,output,compiler='gp'):
 assert not output.exists()
 root=Path(__file__).resolve().parents[1]
 spec=importlib.util.spec_from_file_location('sfc_branch_vm_support',root/'tests/test_linux_microduck_vm.py')
 support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
 receipt={'status':'RUNNING','real_GP':compiler=='gp','real_JS_compiler':compiler=='javascript','real_VM':True,'hardware_access':False,'browser_access':False,
          'VM_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
          'C_host_sha256':hashlib.sha256(host.read_bytes()).hexdigest(),
          'C_source_sha256':hashlib.sha256((root/'common/automation/steps.c').read_bytes()).hexdigest(),'cases':[]}
 assert receipt['C_source_sha256']=='4b36b9cce5729809eeb7bb6d694a2137a13471377ce8b47bf04f2a36ed375c23'
 def case(name,scenario,exhaust=False):
  compiled=json.loads((reports/(name+'.json')).read_text());assert compiled['status']=='PASS'
  result=compiled['result'];script_ids=result.get('script_ids',[128,129]);owner=script_ids[0];heartbeat=script_ids[1] if len(script_ids)>1 else None
  plan=result['worker_plans'][0];indices=result['variables'];prefix=plan['prefix']
  record={'name':name,'scenario':scenario,'checks':[],'states':[],'worker_count':plan['worker_count'],
          'compiler_sha256':hashlib.sha256((reports/(name+'.json')).read_bytes()).hexdigest()}
  receipt['cases'].append(record)
  with tempfile.TemporaryDirectory(prefix='sfc-branch-'+name+'-') as temporary:
   data=Path(temporary)/'data';data.mkdir(mode=0o700);rt=support.Runtime(binary,data,None);vm=rt.wire
   try:
    for c in result['chunks']:
     code=bytes(c['bytes']);code+=b'\0'*(-len(code)%4);vm.upload(c['id'],code,c['kind'])
    def get(name):
     start=len(vm.events);vm.short(7,indices[name]);body=vm.wait(lambda e:e[:2]==(21,indices[name]),start)[2]
     if body[0]==1:return struct.unpack('<i',body[1:5])[0]
     if body[0]==3:return bool(body[1])
     raise AssertionError('Unexpected variable type '+body.hex())
    values={}
    def set_values(**updates):
     for name,value in updates.items():
      body=bytes([3,int(value)]) if isinstance(value,bool) else bytes([1])+struct.pack('<i',value)
      vm.long(8,indices[name],body);values[name]=value
     vm.ping()
    def check(label,condition):assert condition,label;record['checks'].append(label)
    def until(condition,seconds=5):
     deadline=time.monotonic()+seconds
     while time.monotonic()<deadline:
      if condition():return
      vm.pump(.005)
     raise TimeoutError('Branch state did not arrive; '+str({n:get(n) for n in [prefix+'status',prefix+'active',prefix+'run','Completed'] if n in indices}))
    oracle=COracle(host,plan)
    def settle(label,updates=None):
     if updates:set_values(**updates)
     expected=oracle.settle(values)
     until(lambda:get(prefix+'active')==expected)
     for i,var in plan['steps']:
      if expected&(1<<(i-1)):until(lambda i=i:get(prefix+'setup'+str(i)) is True)
     check('C oracle: '+label,get(prefix+'active')==expected)
     public={var:get(var) for i,var in plan['steps']}
     check('shared step flags: '+label,all(public[var] is bool(expected&(1<<(i-1))) for i,var in plan['steps']))
     record['states'].append({'label':label,'expected_C_mask':expected,'public_steps':public})
     return expected
    def complete(count):
     settle('completion '+str(count),{'Done':True});until(lambda:get('Completed')==count and get(prefix+'status')==0)
     check('workers terminated after cycle '+str(count),all(get(prefix+'done'+str(i)) is True for i,name in plan['steps']))
    if exhaust:
     # Manual concurrent scripts are deliberately absent from the static project
     # estimate. They demonstrate real runtime exhaustion rather than a mock gate.
     for chunk in [240,241,242]:
      p=support.Program();loop=len(p.code)//2;p.push(10).op(33,1);offset=loop-(len(p.code)//2+1);p.op(22,offset)
      vm.upload(chunk,p.finish(),1);vm.short(3,chunk)
     vm.short(3,heartbeat);vm.short(3,owner)
     until(lambda:get(prefix+'status')==-1,3)
     check('capacity failure occurs before any setup action',all(get(name)==0 for name in indices if name.endswith('Entry')))
     check('capacity failure cannot fall through after the chart',get('Completed')==0)
     check('capacity failure clears owned running flag',get(prefix+'run') is False)
     check('actual VM reported task exhaustion',any(b'No free task entries' in e[2] for e in vm.events))
     until(lambda:all(get(prefix+'done'+str(i)) is True for i,var in plan['steps'] if get(prefix+'ready'+str(i)) is True))
     check('allocated workers exit after failed admission',get(prefix+'active')==0)
     check('released task entries accept another real reporter',rt.execute(support.Program().push(12).finish(),chunk=254)==12)
    elif scenario=='immediate-reentry':
     set_values(Gate=True,Join=True,Done=True)
     vm.short(3,heartbeat);vm.short(3,owner)
     until(lambda:get('Completed')==2 and get(prefix+'status')==0)
     check('immediate cycles preserve persistent true guards',get('Gate') is True and get('Join') is True and get('Done') is True)
     check('all setup actions run once per immediate entry',all(get(name)==2 for name in indices if name.endswith('Entry')))
     check('all workers finish after immediate reentry',all(get(prefix+'done'+str(i)) is True for i,var in plan['steps']))
     check('terminal completion clears all public flags',all(get(var) is False for i,var in plan['steps']))
    else:
     vm.short(5,1);settle('initial')
     if scenario=='and-deep':
      settle('numeric gate stays false',{'Gate':1})
      settle('three simultaneous branches',{'Gate':True})
      check('setup sees peer already active',get('PeerSeen') is True)
      a,b,h=get('B1Loop'),get('B2Loop'),get('Heartbeat');vm.pump(.06)
      check('waiting action does not block other branch or script',get('B2Loop')>b and get('Heartbeat')>h)
      settle('shared fork condition is not required after activation',{'Gate':False,'Join':True})
      settle('first branch reaches final early',{'Move1':True});check('join waits for other final steps',get('AfterEntry')==0)
      f=get('F1Loop');vm.pump(.02);check('early final loop continues while waiting',get('F1Loop')>f)
      settle('second branch reaches final',{'Move2':True});check('third branch still gates join',get('AfterEntry')==0)
      settle('early true join releases only after all final steps',{'Move3':True});check('join runs next setup once',get('AfterEntry')==1)
      complete(1)
      set_values(Gate=False,Join=False,Done=False,Move1=False,Move2=False,Move3=False);oracle=COracle(host,plan);vm.short(3,owner)
      settle('reentry initial');settle('reentry fork',{'Gate':True});settle('all finals wait on false join',{'Move1':True,'Move2':True,'Move3':True})
      check('false shared join blocks all ready branches',get('AfterEntry')==1)
      settle('reentry join',{'Join':True});complete(2)
      check('setup executes exactly once per entry across cycles',all(get(name)==2 for name in indices if name.endswith('Entry')))
     elif scenario in ['or','or-six']:
      n=plan['worker_count']-2
      if 'Gate' in indices:
       choices={'Choice'+str(i):False for i in range(1,n+1)}
       choices.update({'Choice'+str(n):True} if scenario=='or-six' else {'Choice2':True,'Choice3':True})
       settle('choices wait on shared gate',dict(choices,Gate=False));gate={'Gate':True}
      else:gate={'Choice3':True}
      settle('ordered alternative choice',gate)
      chosen='B6' if scenario=='or-six' else 'B2' if 'Gate' in indices else 'B3'
      check('only selected alternative setup executes',all(get('B'+str(i)+'Entry')==int('B'+str(i)==chosen) for i in range(1,n+1)))
      settle('OR merge shared transition',{'Join':True});complete(1)
      updates=dict({'Choice'+str(i):True for i in range(1,n+1)},Join=False,Done=False)
      if 'Gate' in indices:updates['Gate']=False
      set_values(**updates);oracle=COracle(host,plan);vm.short(3,owner);settle('OR reentry waiting') if 'Gate' in indices else None
      settle('all true chooses first',{'Gate':True} if 'Gate' in indices else {})
      check('top-to-bottom OR priority on competing true conditions',all(get('B'+str(i)+'Entry')==int(i==1)+int(chosen=='B'+str(i)) for i in range(1,n+1)))
      settle('second merge',{'Join':True});complete(2)
     elif scenario=='nested':
      settle('outer AND with inner OR',{'Gate':True,'Pick1':True,'Pick2':True,'Join':True})
      check('outer join waits for nested convergence',get('EA')==0 and get('E1')==1 and get('E2')==0)
      settle('nested merge permits outer join',{'Merge':True});check('nested merge reached left terminal and final setup',get('EE')==1 and get('EA')==1)
      complete(1)
     else:
      settle('configurable parallel count',{'Gate':True})
      check('configured branches all active and initialized',all(get('B'+str(i)+'Entry')==1 for i in range(1,plan['worker_count']-1)))
      check('shared convergence condition gates ready branches',get('AfterEntry')==0)
      settle('shared join',{'Join':True});complete(1)
    record.update(status='PASS',C_snapshots=len(oracle.states),wire_events=len(vm.events))
   except BaseException as e:record.update(status='FAIL',error=type(e).__name__+': '+str(e));raise
   finally:
    rt.stop();log=(data/'runtime.log').read_text();record['runtime_log']=log
    assert not any(x in log for x in ['AddressSanitizer','runtime error:','LeakSanitizer']),log
    output.write_text(json.dumps(receipt,indent=2)+'\n')
  print(name,scenario,len(record['checks']),'PASS',flush=True)
 try:
  case('and-3-deep','and-deep')
  case('or-3','or');case('or-3-no-common','or');case('or-6','or-six')
  for name in ['and-2','and-4','and-6']:case(name,'and-configurable')
  case('nested-and-or','nested');case('and-3-deep','pool-exhaustion',True)
  case('and-2-repeat','immediate-reentry')
  receipt['status']='PASS'
 except BaseException as e:receipt.update(status='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:output.write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for flag in ['binary','host','reports','output']:p.add_argument('--'+flag,type=Path,required=True)
 p.add_argument('--compiler',choices=['gp','javascript'],default='gp')
 a=p.parse_args();run(a.binary.resolve(),a.host.resolve(),a.reports.resolve(),a.output.resolve(),a.compiler)
