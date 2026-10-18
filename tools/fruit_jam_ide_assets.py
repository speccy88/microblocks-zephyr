"""Verified real GP editor patch and assets shared by USB and native hosting."""
# SPDX-License-Identifier: MPL-2.0
import hashlib,json,re
from patch_ide import patch_ide


def patch_package(javascript,data,library):
    javascript,data=patch_ide(javascript,data,library)
    source=javascript.decode('utf-8')
    match=re.search(r'loadPackage\((\{files:\[.*?\],remote_package_size:\d+\})\)',source)
    if not match: # patch_ide serializes quoted JSON keys.
        match=re.search(r'loadPackage\((\{"files":\[.*?\],"remote_package_size":\d+\})\)',source)
    metadata=json.loads(match[1])
    output=bytearray();entries=[]
    for item in metadata['files']:
        name=item['filename']
        payload=data[item['start']:item['end']]
        replacements=[(b"atPut primsets 'rlcd'",b"atPut primsets 'fruitJam'"),
            (b'rlcd.loadLibrary',b'fruitJam.loadLibrary'),(b'rlcd.openExample',b'fruitJam.openExample'),
            (b'Waveshare_RLCD_4_2.ubl',b'Fruit_Jam.ubl'),(b'Waveshare RLCD 4.2',b'Fruit Jam'),
            (b'Examples/Waveshare/',b'Examples/Fruit Jam/')]
        for before,after in replacements:payload=payload.replace(before,after)
        name=name.replace('Waveshare_RLCD_4_2.ubl','Fruit_Jam.ubl').replace('Examples/Waveshare/','Examples/Fruit Jam/')
        start=len(output);output.extend(payload)
        entries.append(dict(filename=name,start=start,end=len(output)))
    metadata=dict(files=entries,remote_package_size=len(output))
    source=source[:match.start(1)]+json.dumps(metadata,separators=(',',':'))+source[match.end(1):]
    source=source.replace('"/Examples","Waveshare"','"/Examples","Fruit Jam"')
    gate="""Module.preRun.push(function() {
 addRunDependency('board-english');
 Promise.resolve(GetText.ready).then(function(){removeRunDependency('board-english');},
 function(){Module.setStatus('Cannot load local language assets. Reload to retry.');});
});
"""
    return (gate+source).encode(),bytes(output)


def prepare_assets(repo,source):
    manifest=json.loads((repo/'dependencies/ide-assets.json').read_text())
    expected={item['path']:item['sha256'] for item in manifest['files']}
    originals={}
    for name in ('gp_wasm.js','gp_wasm.data','microblocks.html','gettext.js'):
        raw=(source/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected[name]:raise ValueError('IDE source changed: '+name)
        originals[name]=raw
    js,data=patch_package(originals['gp_wasm.js'],originals['gp_wasm.data'],
        (repo/'boards/adafruit_fruit_jam/integration/Fruit_Jam.ubl').read_bytes())
    html,count=re.subn(rb'(<script[^>]+src="gp_wasm\.js[^\"]*")',rb'\1 defer',originals['microblocks.html'])
    assert count==1
    hook=b"document.addEventListener('ready', () => { IDE.init(); });"
    assert html.count(hook)==1
    html=html.replace(hook,b"document.addEventListener('ready', () => { IDE.init(); document.dispatchEvent(new Event('board-ide-ready')); });")
    gettext=originals['gettext.js']
    for before,after in [(b"GetText.readLocale('en');",b"GetText.ready = GetText.readLocale('en');"),
        (b"\tfetch('translations/' + langcode + '.po')",b"\treturn fetch('translations/' + langcode + '.po')"),
        (b"GetText.setLocale = function (langcode) {",b"GetText.setLocale = function (langcode) {\n\tif (!langcode) { langcode = 'en'; }")]:
        assert gettext.count(before)==1
        gettext=gettext.replace(before,after)
    network=(repo/'web/board-network.js').read_text(encoding='utf-8')
    network=network.replace('Waveshare','Fruit Jam').replace('rlcd.','fruitJam.')
    network='\n'.join(line for line in network.splitlines() if "wifi=document.createElement('a')" not in line)+'\n'
    return {'gp_wasm.js':js,'gp_wasm.data':data,'microblocks.html':html,
            'gettext.js':gettext,'unoq-network.js':network.encode()}


def native_bootstrap(html):
    """Serialize real editor startup for the six-slot NINA native HTTP host.

    The USB host keeps prepare_assets() unchanged. Blocking scripts and their
    inline neighbors execute first in original order, then deferred scripts.
    """
    text=html.decode('utf-8');blocking=[];deferred=[]
    def script(match):
        attrs,body=match.groups()
        source=re.search(r'\bsrc="([^"]+)"',attrs)
        entry={'src':source[1]} if source else {'inline':body}
        (deferred if re.search(r'\bdefer\b',attrs) else blocking).append(entry)
        return ''
    text=re.sub(r'<script\b([^>]*)>(.*?)</script>',script,text,flags=re.S)
    assert len(blocking)==10 and len(deferred)==6
    assert deferred[-1]['src'].startswith('gp_wasm.js?')
    text=re.sub(r'(<link\b[^>]*rel="stylesheet"[^>]*?)\bhref=',r'\1data-fj-href=',text)
    text=re.sub(r'(<img\b[^>]*?)\bsrc=',r'\1data-fj-src=',text)
    config=json.dumps(blocking+deferred,separators=(',',':')).replace('<','\\u003c')
    bootstrap=r"""
<script id="fruit-jam-native-bootstrap">
(() => {
 const scripts=FJ_SCRIPTS;
 const root=document.documentElement;root.dataset.fjBootstrap='loading';
 document.addEventListener('board-ide-ready',()=>{root.dataset.fjBootstrap='ready';},{once:true});
 const resource=(node,attribute,url)=>new Promise((resolve,reject)=>{
  if(new URL(url,location.href).origin!==location.origin){reject(new Error('External startup resource'));return;}
  const timer=setTimeout(()=>reject(new Error('Resource deadline: '+url)),20000);
  node.onload=()=>{clearTimeout(timer);resolve();};
  node.onerror=()=>{clearTimeout(timer);reject(new Error('Resource load: '+url));};
  node[attribute]=url;
 });
 const run=async()=>{
  try {
   for(const node of document.querySelectorAll('link[data-fj-href]'))await resource(node,'href',node.dataset.fjHref);
   for(const node of document.querySelectorAll('img[data-fj-src]'))await resource(node,'src',node.dataset.fjSrc);
   for(const entry of scripts){
    const node=document.createElement('script');
    if(entry.src){
     node.async=false;
     const pending=resource(node,'src',entry.src);document.head.appendChild(node);await pending;
    }else{node.textContent=entry.inline;document.head.appendChild(node);}
   }
   if(root.dataset.fjBootstrap!=='ready')root.dataset.fjBootstrap='scripts-loaded';
  }catch(error){
   root.dataset.fjBootstrap='failed';console.error(error);
   const notice=document.querySelector('.app-preloader__text');
   if(notice)notice.textContent='Cannot load the editor from Fruit Jam. Reload to retry.';
  }
 };
 if(document.readyState==='complete')run();else window.addEventListener('load',run,{once:true});
})();
</script>
""".replace('FJ_SCRIPTS',config)
    assert text.count('</body>')==1
    return text.replace('</body>',bootstrap+'</body>').encode('utf-8')
