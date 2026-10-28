#!/usr/bin/env python3
"""Add the reviewed static JS subtree to an identical GP build. Never deploy."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,os
from pathlib import Path,PurePosixPath
import re,shutil,stat,tempfile,urllib.parse,urllib.request,zipfile

ROOT=Path(__file__).resolve().parents[1]

def require(value,message):
    if not value:raise ValueError(message)

def digest(raw):return hashlib.sha256(raw).hexdigest()

def files(folder):
    require(not folder.is_symlink(),'Symlink root refused')
    out={}
    for p in sorted(folder.rglob('*')):
        require(not p.is_symlink(),'Symlink in static build')
        if p.is_file():out[p.relative_to(folder).as_posix()]=digest(p.read_bytes())
    return out

def safe_name(name):
    return isinstance(name,str) and bool(name) and '\\' not in name and ':' not in name and not name.startswith('/') and all(p not in ('','.','..') for p in name.split('/')) and not any(ord(c)<32 for c in name)

def config(value):
    require(isinstance(value,dict) and value.get('schema')==1,'Preview manifest schema')
    for key in ('archive_sha256','gp_manifest_sha256','site_manifest_sha256'):
        require(isinstance(value.get(key),str) and re.fullmatch('[0-9a-f]{64}',value[key]),'Preview digest required')
    for key in ('gp_source_commit','editor_source_commit'):
        require(isinstance(value.get(key),str) and re.fullmatch('[0-9a-f]{40}',value[key]),'Exact source pin required')
    require(type(value.get('archive_bytes')) is int and 0<value['archive_bytes']<=64*1024*1024,'Archive size bound')
    require(type(value.get('file_count')) is int and 0<value['file_count']<=10000,'Archive file count bound')
    expected='https://github.com/speccy88/microblocks-zephyr/releases/download/'+value.get('release_tag','')+'/gp-with-js-preview-preserved.zip'
    require(isinstance(value.get('release_tag'),str) and re.fullmatch('[A-Za-z0-9._-]{1,100}',value['release_tag']) and value.get('asset_url')==expected,'Reviewed release URL required')
    return value

class GitHubHTTPS(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        u=urllib.parse.urlsplit(newurl)
        require(u.scheme=='https' and u.port in (None,443) and not u.username and not u.password and (u.hostname=='github.com' or (u.hostname or '').endswith('.githubusercontent.com')),'Untrusted download redirect')
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def download(m,path):
    config(m);require(not path.exists(),'Choose a new download path')
    count=0;h=hashlib.sha256()
    with urllib.request.build_opener(GitHubHTTPS()).open(m['asset_url'],timeout=30) as response,path.open('xb') as output:
        while True:
            raw=response.read(1024*1024)
            if not raw:break
            count+=len(raw);require(count<=m['archive_bytes'],'Downloaded archive exceeds bound');h.update(raw);output.write(raw)
    require(count==m['archive_bytes'] and h.hexdigest()==m['archive_sha256'],'Downloaded archive hash/size mismatch')

def install(archive,gp,m):
    config(m);archive=Path(archive);gp=Path(gp)
    require(archive.stat().st_size==m['archive_bytes'] and digest(archive.read_bytes())==m['archive_sha256'],'Archive hash/size mismatch')
    require(gp.is_dir() and not gp.is_symlink() and not (gp/'js-preview').exists(),'Fresh GP build required')
    original=files(gp);require(original.get('linux-preview-manifest.json')==m['gp_manifest_sha256'],'GP snapshot manifest mismatch')
    with zipfile.ZipFile(archive) as z:
        items=z.infolist();require(len(items)==m['file_count'],'Archive count mismatch')
        names=[i.filename for i in items]
        require(len(set(names))==len(names) and len({n.casefold() for n in names})==len(names),'Duplicate archive path')
        total=0
        for item in items:
            require(safe_name(item.filename) and not item.is_dir(),'Unsafe archive path')
            require(stat.S_IFMT(item.external_attr>>16) in (0,stat.S_IFREG) and not item.flag_bits&1,'Non-regular/encrypted archive entry')
            require(item.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) and 0<=item.file_size<=32*1024*1024,'Archive member bound')
            total+=item.file_size
        require(total<=512*1024*1024,'Archive total bound')
        name='js-preview/site-manifest.json';require(name in names and z.getinfo(name).file_size<=2*1024*1024,'Site manifest missing/oversized')
        raw=z.read(name);require(digest(raw)==m['site_manifest_sha256'],'Site manifest hash mismatch');site=json.loads(raw)
        require(site.get('gp_files_preserved')==original and site.get('upstream_engine_modified') is False and site.get('runtime_upgraded') is False,'GP or engine preservation mismatch')
        expected=site.get('files');require(isinstance(expected,dict) and set(names)==set(expected)|{name},'Unlisted archive entry')
        expected={**expected,name:digest(raw)}
        require(all(safe_name(n) and isinstance(d,str) and re.fullmatch('[0-9a-f]{64}',d) for n,d in expected.items()),'Invalid file digest table')
        require({n:d for n,d in expected.items() if not n.startswith('js-preview/')}==original,'Unexpected non-JS archive file')
        for item in items:
            h=hashlib.sha256();count=0
            with z.open(item) as source:
                while True:
                    block=source.read(1024*1024)
                    if not block:break
                    count+=len(block);require(count<=item.file_size,'Expanded archive bound');h.update(block)
            require(count==item.file_size and h.hexdigest()==expected[item.filename],'Archive file hash mismatch')
        with tempfile.TemporaryDirectory(prefix='owned-js-preview-',dir=gp.parent) as directory:
            stage=Path(directory)/'js-preview';stage.mkdir()
            for item in items:
                if not item.filename.startswith('js-preview/'):continue
                target=stage.joinpath(*PurePosixPath(item.filename).parts[1:]);target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(item) as source,target.open('xb') as output:shutil.copyfileobj(source,output,1024*1024)
            require(files(stage)=={n.removeprefix('js-preview/'):d for n,d in expected.items() if n.startswith('js-preview/')},'Staged JS hash mismatch')
            require(files(gp)==original,'GP changed during JS verification')
            os.replace(stage,gp/'js-preview')
    after=files(gp);require({n:d for n,d in after.items() if not n.startswith('js-preview/')}==original,'GP changed after composition')
    return {'gp_files_preserved':len(original),'js_files_added':len(after)-len(original),'archive_sha256':m['archive_sha256'],'deployment_performed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gp-site',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--fetch',action='store_true');a=p.parse_args()
    m=config(json.loads((ROOT/'dependencies/js-preview-site.json').read_text(encoding='utf-8')))
    if a.fetch:download(m,a.archive)
    print(json.dumps(install(a.archive,a.gp_site,m),indent=2))
