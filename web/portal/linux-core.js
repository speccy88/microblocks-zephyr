/* SPDX-License-Identifier: MIT */
/* Pure Linux profile and reviewed-release command generation. No I/O. */
(function(root){
 'use strict';
 const REPOSITORY='speccy88/microblocks-zephyr';
 // Linux target documentation follows the published migration branch until main integration.
 const DOCUMENTATION_REF='codex/js-editor-migration-20261027';
 const profiles=Object.freeze({
  'raspberry-pi5':Object.freeze({
   id:'raspberry-pi5',name:'Raspberry Pi 5 - Linux ARM64',placeholder:false,requiresRobotServices:false,
   hardware:'Broadcom BCM2712, Cortex-A76; requires a 64-bit Linux OS.',
   validation:'Standalone native SmallVM core: Pi compilation, bytecode, graphical uploads, browser save/restore and SSH-tunnel reconnect passed. No MicroDuck services are required. Full OS reboot acceptance remains pending; GPIO, camera and audio are unsupported.',
   validationKind:'native-pi-tested',hostPlaceholder:'rpi5.local or an IPv4 address',
   editorPath:'editor/raspberry-pi5/microblocks.html',
   docs:Object.freeze([{label:'Standalone Raspberry Pi 5 target and lifecycle',path:'docs/RASPBERRY_PI_5_STANDALONE.md'},{label:'Linux ARM64 installation and test status',path:'linux/arm64/README.md'},{label:'Portal installation and connection guide',path:'docs/LINUX_PORTAL.md'}])
  }),
  microduck:Object.freeze({
   id:'microduck',name:'MicroDuck Rockchip RK3566',placeholder:true,
   hardware:'Pollen Robotics MicroDuck, Rockchip RK3566 / Cortex-A55, Linux ARM64.',
   validation:'Experimental placeholder. BLE/JSON-RPC mocks and native Pi adapter tests use simulated robot services. No physical MicroDuck validation; installation, services and motion remain unverified. Offline editing and preparation only.',
   validationKind:'experimental-placeholder',hostPlaceholder:'Unavailable for this placeholder',
   editorPath:'editor/microduck/microblocks.html',
   docs:Object.freeze([{label:'MicroDuck BLE and JSON-RPC coverage',path:'docs/MICRODUCK_PROTOCOL.md'},{label:'Linux ARM64 installation and test status',path:'linux/arm64/README.md'},{label:'Portal installation and connection guide',path:'docs/LINUX_PORTAL.md'}])
  })
 });
 class ValidationError extends Error{constructor(message){super(message);this.name='ValidationError';}}
 class ReleaseUnavailableError extends Error{constructor(message){super(message);this.name='ReleaseUnavailableError';}}
 const fail=message=>{throw new ValidationError(message);};
 function profileInfo(id){if(typeof id!=='string'||!Object.hasOwn(profiles,id))fail('Choose a supported Linux board profile.');return profiles[id];}
 function validateUsername(value){
  if(typeof value!=='string'||!/^[A-Za-z_][A-Za-z0-9_-]{0,31}$/.test(value))fail('Enter a Linux SSH username (letters, digits, underscore or hyphen; no options or spaces).');
  return value;
 }
 function validateHost(value){
  if(typeof value!=='string'||value.length<1||value.length>253||/[\x00-\x20\x7f-\uffff]/.test(value))fail('Enter an IPv4 address or DNS hostname without spaces or control characters.');
  if(/^[0-9.]+$/.test(value)){
   const parts=value.split('.');
   if(parts.length!==4||parts.some(p=>!/^(0|[1-9][0-9]{0,2})$/.test(p)||Number(p)>255)||Number(parts[0])===0||Number(parts[0])>=224)fail('Enter a canonical unicast IPv4 address, such as 192.168.1.105.');
   return value;
  }
  const labels=value.split('.');
  if(labels.some(label=>label.length>63||!/^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(label)))fail('Enter a DNS hostname or IPv4 address; URLs, ports, IPv6 and SSH options are not accepted here.');
  return value.toLowerCase();
 }
 function validateTarget({username,host}={}){return Object.freeze({username:validateUsername(username),host:validateHost(host)});}
 function releaseReason(manifest){
  return typeof manifest?.reason==='string'&&manifest.reason.length<=400?manifest.reason:'No reviewed ARM64 release is available. Installation command copying is disabled.';
 }
 function validateReleaseManifest(manifest){
  if(!manifest||typeof manifest!=='object'||Array.isArray(manifest)||manifest.schemaVersion!==1)fail('The Linux release manifest is missing or has an unsupported schema.');
  if(manifest.available!==true)throw new ReleaseUnavailableError(releaseReason(manifest));
  if(manifest.repository!==undefined&&manifest.repository!==REPOSITORY)fail('The release must belong to the reviewed MicroBlocks repository.');
  const version=manifest.version;
  if(typeof version!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(version)||['latest','main','master','head'].includes(version.toLowerCase()))fail('A pinned release tag is required; moving aliases are not accepted.');
  function hash(value,length,label){if(typeof value!=='string'||!(new RegExp('^[a-fA-F0-9]{'+length+'}$')).test(value)||/^0+$/.test(value))fail('A reviewed '+label+' is required.');return value.toLowerCase();}
  const artifactSHA256=hash(manifest.artifactSHA256,64,'artifact SHA-256');
  const installerCommit=hash(manifest.installerCommit,40,'installer commit');
  const installerSHA256=hash(manifest.installerSHA256,64,'installer SHA-256');
  return Object.freeze({schemaVersion:1,available:true,repository:REPOSITORY,version,artifactSHA256,installerCommit,installerSHA256,
   installerURL:'https://raw.githubusercontent.com/'+REPOSITORY+'/'+installerCommit+'/scripts/install-smallvm-linux-arm64.sh',
   artifactURL:'https://github.com/'+REPOSITORY+'/releases/download/'+version+'/smallvm-linux-arm64-'+version+'.tar.gz',
   releaseURL:'https://github.com/'+REPOSITORY+'/releases/tag/'+version});
 }
 function remoteInstallScript(release,{service=false}={}){
  const r=validateReleaseManifest(release);
  if(typeof service!=='boolean')fail('The user-service choice must be explicit.');
  return [
   'set -euo pipefail',
   'umask 077',
   'for tool in bash curl sha256sum mktemp; do command -v "$tool" >/dev/null || { printf "Missing dependency: %s\\n" "$tool" >&2; exit 1; }; done',
   'work=$(mktemp -d "${TMPDIR:-/tmp}/microblocks-install.XXXXXXXX")',
   'trap \'rm -rf -- "$work"\' EXIT',
   'script="$work/install-smallvm-linux-arm64.sh"',
   'curl --fail --silent --show-error --location --proto \'=https\' --tlsv1.2 --max-filesize 1048576 \\',
   '  \''+r.installerURL+'\' -o "$script"',
   'if ! printf \'%s  %s\\n\' \''+r.installerSHA256+'\' "$script" | sha256sum --check --status; then',
   '  printf "Installer checksum failed; nothing executed.\\n" >&2; exit 1',
   'fi',
   'bash "$script" --version \''+r.version+'\' --sha256 \''+r.artifactSHA256+'\''+(service?' --service':''),
   ''
  ].join('\n');
 }
 function asciiBase64(text){
  if(typeof root.btoa==='function')return root.btoa(text);
  if(typeof Buffer!=='undefined')return Buffer.from(text,'ascii').toString('base64');
  fail('This browser cannot encode the reviewed installation command.');
 }
 function generateInstallCommands({profile,username,host,release,service=false}={}){
  const board=profileInfo(profile);
  if(board.placeholder)fail(board.name+' is an experimental placeholder; installation is not available.');
  const target=validateTarget({username,host}),pinned=validateReleaseManifest(release);
  const remoteScript=remoteInstallScript(pinned,{service}),encoded=asciiBase64(remoteScript);
  // The remote argument has no inner quotes, dollars, backticks or newlines.
  // This survives both PowerShell's native-argument handling and POSIX shells.
  const remoteCommand='printf %s '+encoded+' | base64 -d | bash';
  const command='ssh -o StrictHostKeyChecking=yes '+target.username+'@'+target.host+' "'+remoteCommand+'"';
  return Object.freeze({profile:board.id,target,posix:command,powershell:command,remoteScript,remoteCommand,
   installerURL:pinned.installerURL,artifactURL:pinned.artifactURL,releaseURL:pinned.releaseURL,version:pinned.version});
 }
 function validateWSSEndpoint(value){
  if(typeof value!=='string'||value.length>512||/[\x00-\x20\x7f]/.test(value))fail('Enter a trusted wss:// endpoint without spaces or control characters.');
  let url;try{url=new URL(value);}catch{fail('Enter an absolute trusted wss:// endpoint.');}
  if(url.protocol!=='wss:'||url.username||url.password||url.search||url.hash||value.includes('?')||value.includes('#'))fail('Use wss:// with a trusted certificate, without credentials, query parameters or fragments.');
  validateHost(url.hostname);
  if(url.pathname!=='/ws/vm')fail('The SmallVM bridge endpoint must use /ws/vm.');
  return url.href;
 }
 const api=Object.freeze({REPOSITORY,DOCUMENTATION_REF,profiles,ValidationError,ReleaseUnavailableError,profileInfo,validateUsername,validateHost,validateTarget,validateReleaseManifest,releaseReason,remoteInstallScript,generateInstallCommands,validateWSSEndpoint});
 root.MicroBlocksLinux=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window==='undefined'?globalThis:window);
