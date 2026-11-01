// SPDX-License-Identifier: MIT
// Pure command and DOM tests. No generated SSH/installation command is executed.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');
const core=require('../web/portal/linux-core.js');
const {mount}=require('../web/portal/linux-panel.js');
const unpublished=require('../web/portal/linux-release.json');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const reviewedFixture=()=>({schemaVersion:1,available:true,repository:core.REPOSITORY,
 version:'linux-arm64-v417.test1',artifactSHA256:hash('non-release archive fixture'),
 installerCommit:'1234567890abcdef1234567890abcdef12345678',installerSHA256:hash('non-release installer fixture')});
const target={profile:'raspberry-pi5',username:'fred',host:'192.168.1.105'};

test('checked-in release manifest disables every installation command',()=>{
 assert.equal(unpublished.available,false);
 assert.throws(()=>core.generateInstallCommands({...target,release:unpublished}),core.ReleaseUnavailableError);
 assert.throws(()=>core.remoteInstallScript(unpublished),core.ReleaseUnavailableError);
 assert.equal(unpublished.version,null);assert.equal(unpublished.artifactSHA256,null);
});

test('profiles distinguish real native Pi tests from simulated MicroDuck coverage',()=>{
 assert.equal(core.profileInfo('raspberry-pi5').validationKind,'native-pi-tested');
 assert.match(core.profileInfo('raspberry-pi5').validation,/graphical uploads.*passed/);
 assert.match(core.profileInfo('raspberry-pi5').validation,/OS reboot.*pending/);
 assert.equal(core.profileInfo('raspberry-pi5').requiresRobotServices,false);
 assert.equal(core.profileInfo('raspberry-pi5').placeholder,false);
 assert.equal(core.profileInfo('microduck').name,'MicroDuck Rockchip RK3566');
 assert.equal(core.profileInfo('microduck').validationKind,'experimental-placeholder');
 assert.equal(core.profileInfo('microduck').placeholder,true);
 assert.match(core.profileInfo('microduck').validation,/No physical MicroDuck/);
 for(const name of ['p4','__proto__','constructor','',undefined])assert.throws(()=>core.profileInfo(name));
});

test('SSH usernames and canonical IPv4/DNS targets are accepted without options',()=>{
 for(const username of ['fred','pi','_service','Robot_User-1'])assert.equal(core.validateUsername(username),username);
 for(const host of ['192.168.1.105','10.0.0.1','127.0.0.1','rpi5','rpi5.local','robot-1.example.net','xn--robot-2qa.local'])assert.equal(core.validateHost(host),host);
 assert.equal(core.validateHost('RPI5.LOCAL'),'rpi5.local');
 assert.deepEqual(core.validateTarget({username:'fred',host:'RPI5'}),{username:'fred',host:'rpi5'});
});

test('target validation rejects shell/control injection, SSH options and malformed addresses',()=>{
 for(const username of ['-oProxyCommand=id','fred;touch bad','fred user','fred@host','fred\n','fred\0','fred$(id)','fred`id`',"fred'",'fred/../../','x'.repeat(33)])assert.throws(()=>core.validateUsername(username),core.ValidationError,username);
 for(const host of ['-oProxyCommand=id','host;id','host$(id)','host`id`','host\n','host\0','host name','192.168.1.105 -p 22',
  '192.168.01.1','256.1.1.1','0.0.0.0','224.0.0.1','255.255.255.255','123','127.1','1.2.3.4.5',
  'ssh://robot.local','user@robot.local','robot.local:22','[::1]','robot_.local','-robot.local','robot-.local','.local','robot..local','robot.local/','robot.local%0a','é.local','x'.repeat(254)])assert.throws(()=>core.validateHost(host),core.ValidationError,host);
});

test('release metadata must pin the binary digest and installer commit plus digest',()=>{
 const good=reviewedFixture(),validated=core.validateReleaseManifest(good);
 assert.match(validated.installerURL,new RegExp('/'+good.installerCommit+'/scripts/install-smallvm-linux-arm64.sh$'));
 assert.equal(validated.artifactURL,'https://github.com/'+core.REPOSITORY+'/releases/download/'+good.version+'/smallvm-linux-arm64-'+good.version+'.tar.gz');
 for(const field of ['version','artifactSHA256','installerCommit','installerSHA256']){
  const missing={...good};delete missing[field];assert.throws(()=>core.validateReleaseManifest(missing),core.ValidationError);
 }
 for(const version of ['latest','LATEST','main','master','HEAD','v417;id',"v417'",'v417\n','../v417'])assert.throws(()=>core.validateReleaseManifest({...good,version}));
 for(const field of ['artifactSHA256','installerSHA256'])for(const value of ['0'.repeat(64),'a'.repeat(63),'z'.repeat(64),hash('fixture')+';id'])assert.throws(()=>core.validateReleaseManifest({...good,[field]:value}));
 assert.throws(()=>core.validateReleaseManifest({...good,installerCommit:'main'}));
 assert.throws(()=>core.validateReleaseManifest({...good,repository:'attacker/project'}));
 assert.throws(()=>core.validateReleaseManifest({...good,schemaVersion:2}));
});

test('PowerShell and POSIX commands preserve one reviewable encoded remote argument',()=>{
 for(const profile of ['raspberry-pi5']){
  const release=reviewedFixture(),result=core.generateInstallCommands({...target,profile,release});
  assert.equal(result.powershell,result.posix);
  assert.match(result.posix,/^ssh -o StrictHostKeyChecking=yes fred@192\.168\.1\.105 "printf %s [A-Za-z0-9+/=]+ \| base64 -d \| bash"$/);
  assert.equal(result.posix.includes('\n'),false);assert.equal(result.posix.includes('$'),false);assert.equal(result.posix.includes('`'),false);
  const encoded=result.remoteCommand.match(/^printf %s ([A-Za-z0-9+/=]+) \| base64 -d \| bash$/)[1];
  assert.equal(Buffer.from(encoded,'base64').toString('ascii'),result.remoteScript);
  assert.match(result.remoteScript,/^set -euo pipefail\numask 077\n/);
  assert.match(result.remoteScript,/mktemp -d "\$\{TMPDIR:-\/tmp\}\/microblocks-install\.XXXXXXXX"/);
  assert.match(result.remoteScript,/trap 'rm -rf -- "\$work"' EXIT/);
  assert.match(result.remoteScript,/--proto '=https' --tlsv1\.2/);
  assert.ok(result.remoteScript.includes(release.installerSHA256));
  assert.ok(result.remoteScript.indexOf('sha256sum --check --status')<result.remoteScript.indexOf('bash "$script" --version'));
  assert.ok(result.remoteScript.includes("--version '"+release.version+"' --sha256 '"+release.artifactSHA256+"'"));
  assert.equal(result.remoteScript.includes('--service'),false);
  const curlLine=result.remoteScript.split('\n').find(line=>line.startsWith('curl '));
  assert.ok(curlLine.endsWith(' \\'));assert.equal(curlLine.endsWith(' \\\\'),false);
 }
});

test('MicroDuck placeholder cannot produce an install command even with a valid future ARM64 release',()=>{
 assert.throws(()=>core.generateInstallCommands({...target,profile:'microduck',release:reviewedFixture()}),/experimental placeholder.*installation is not available/);
});

test('service flag is an explicit boolean choice and no secrets enter commands',()=>{
 const result=core.generateInstallCommands({...target,release:reviewedFixture(),service:true});
 assert.match(result.remoteScript,/--service\n$/);
 for(const service of ['yes',1,null])assert.throws(()=>core.generateInstallCommands({...target,release:reviewedFixture(),service}));
 assert.doesNotMatch(result.remoteScript,/password|authorized_keys|ssh-add|sudo|curl[^\n]*\|\s*bash/i);
});

test('browser encoding path produces the same command without Node globals',()=>{
 const window={btoa:text=>Buffer.from(text,'ascii').toString('base64')};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/portal/linux-core.js'),'utf8'),{window,URL});
 const generated=window.MicroBlocksLinux.generateInstallCommands({...target,release:reviewedFixture()});
 assert.equal(generated.posix,core.generateInstallCommands({...target,release:reviewedFixture()}).posix);
});

test('optional WSS endpoints reject insecure transports, URL secrets and alternate paths',()=>{
 assert.equal(core.validateWSSEndpoint('wss://board.example:8443/ws/vm'),'wss://board.example:8443/ws/vm');
 for(const value of ['ws://board.example/ws/vm','http://board.example/ws/vm','wss://user:secret@board.example/ws/vm',
  'wss://board.example/ws/vm?token=secret','wss://board.example/ws/vm?','wss://board.example/ws/vm#fragment',
  'wss://board.example/other','wss://board.example/ws/vm\n','javascript:alert(1)','/ws/vm'])assert.throws(()=>core.validateWSSEndpoint(value));
});

class Element{
 constructor(tag,document){this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.dataset={};this.listeners=new Map();this.attributes={};this.value='';this.disabled=false;this.hidden=false;this._text='';}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 append(...nodes){for(const node of nodes){node.parentNode=this;this.children.push(node);if(this.tagName==='SELECT'&&!this.value)this.value=node.value;}}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 setAttribute(name,value){this.attributes[name]=String(value);}
 addEventListener(name,callback){if(!this.listeners.has(name))this.listeners.set(name,[]);this.listeners.get(name).push(callback);}
 async fire(name){const event={type:name,preventDefault(){this.defaultPrevented=true;}};for(const callback of this.listeners.get(name)||[])await callback(event);}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(child=>child!==this);}
 find(predicate){if(predicate(this))return this;for(const child of this.children){const found=child.find(predicate);if(found)return found;}}
}
function harness(release=unpublished){
 const document={createElement(tag){return new Element(tag,this);}},container=new Element('section',document),copied=[],endpoints=[],editors=[];
 const panel=mount(container,{profile:'raspberry-pi5',releaseManifest:release,username:'fred',host:'192.168.1.105',clipboard:{async writeText(value){copied.push(value);}},onEndpoint:value=>endpoints.push(value),onOpenEditor:value=>editors.push(value)});
 return {container,panel,copied,endpoints,editors,find:predicate=>container.find(predicate)};
}

test('unpublished-release panel disables copy, offers no command and makes no probe',async()=>{
 const h=harness(),button=h.find(e=>e.tagName==='BUTTON'&&e.textContent==='Copy installation command'),area=h.find(e=>e.tagName==='TEXTAREA');
 assert.equal(button.disabled,true);assert.equal(area.value,'');
 await button.fire('click');assert.equal(h.copied.length,0);assert.equal(h.endpoints.length,0);assert.equal(h.editors.length,0);
 assert.match(h.container.textContent,/no reviewed ARM64 GitHub Release is published/i);
 const guide=h.find(e=>e.tagName==='A'&&e.textContent==='Standalone Raspberry Pi 5 target and lifecycle');
 assert.equal(guide.href,'https://github.com/'+core.REPOSITORY+'/blob/codex/js-editor-migration-20261027/docs/RASPBERRY_PI_5_STANDALONE.md');
 h.panel.destroy();assert.equal(h.container.children.length,0);
});

test('reviewed command is copied only by explicit click and is revoked after release removal',async()=>{
 const h=harness(reviewedFixture()),button=h.find(e=>e.tagName==='BUTTON'&&e.textContent==='Copy installation command'),area=h.find(e=>e.tagName==='TEXTAREA');
 assert.equal(button.disabled,false);assert.equal(h.copied.length,0);assert.equal(area.readOnly,true);
 const expected=core.generateInstallCommands({...target,release:reviewedFixture()});
 assert.equal(area.value,expected.powershell);assert.ok(h.container.textContent.includes(expected.remoteScript));
 await button.fire('click');assert.deepEqual(h.copied,[expected.powershell]);
 h.panel.setReleaseManifest(unpublished);assert.equal(button.disabled,true);assert.equal(area.value,'');
 await button.fire('click');assert.equal(h.copied.length,1);
});

test('invalid fields and profile switches clear stale install targets',async()=>{
 const h=harness(reviewedFixture()),button=h.find(e=>e.tagName==='BUTTON'&&e.textContent==='Copy installation command'),host=h.find(e=>e.name==='host'),username=h.find(e=>e.name==='username');
 host.value='192.168.1.105;id';await host.fire('input');assert.equal(button.disabled,true);
 host.value='192.168.1.105';await host.fire('input');assert.equal(button.disabled,false);
 h.panel.setProfile('microduck');assert.equal(host.value,'');assert.equal(username.value,'');assert.equal(button.disabled,true);
 assert.match(h.container.textContent,/No physical MicroDuck validation/);
});

test('placeholder panel disables install, service and endpoint paths but keeps offline editing',async()=>{
 const h=harness(reviewedFixture());h.panel.setProfile('microduck');
 const copy=h.find(e=>e.tagName==='BUTTON'&&e.textContent==='Copy installation command');
 const endpoint=h.find(e=>e.tagName==='INPUT'&&e.type==='url');
 const use=h.find(e=>e.tagName==='BUTTON'&&e.textContent==='Use endpoint for the editor');
 for(const name of ['host','username'])assert.equal(h.find(e=>e.name===name).disabled,true);
 assert.equal(h.find(e=>e.type==='checkbox').disabled,true);
 assert.equal(copy.disabled,true);assert.equal(endpoint.disabled,true);assert.equal(use.disabled,true);
 endpoint.value='wss://board.example/ws/vm';await endpoint.fire('input');await use.fire('click');await copy.fire('click');
 assert.equal(use.disabled,true);assert.equal(h.endpoints.length,0);assert.equal(h.copied.length,0);
 const editor=h.find(e=>e.tagName==='A'&&e.textContent==='Open placeholder editor (editing only)');
 assert.ok(editor);await editor.fire('click');assert.deepEqual(h.editors,[{profile:'microduck',endpoint:null}]);
 h.panel.setProfile('raspberry-pi5');assert.equal(h.find(e=>e.name==='host').disabled,false);assert.equal(endpoint.disabled,false);
 assert.equal(endpoint.value,'');assert.equal(copy.disabled,true);
});

test('endpoint selection validates WSS and only passes configuration to a callback',async()=>{
 const h=harness(),endpoint=h.find(e=>e.tagName==='INPUT'&&e.type==='url'),button=h.find(e=>e.tagName==='BUTTON'&&e.textContent==='Use endpoint for the editor');
 endpoint.value='ws://board.example/ws/vm';await endpoint.fire('input');await button.fire('click');assert.equal(h.endpoints.length,0);
 endpoint.value='wss://board.example/ws/vm';await endpoint.fire('input');await button.fire('click');
 assert.deepEqual(h.endpoints,[{profile:'raspberry-pi5',endpoint:'wss://board.example/ws/vm'}]);
 assert.match(h.container.textContent,/Reachability and certificate trust have not been tested/);
});

test('clipboard denial is reported without claiming a successful copy',async()=>{
 const document={createElement(tag){return new Element(tag,this);}},container=new Element('section',document);
 mount(container,{profile:'raspberry-pi5',releaseManifest:reviewedFixture(),username:'fred',host:'rpi5.local',clipboard:{async writeText(){throw Error('denied');}}});
 const button=container.find(e=>e.tagName==='BUTTON'&&e.textContent==='Copy installation command');await button.fire('click');
 assert.match(container.textContent,/browser did not allow copying/);
});
