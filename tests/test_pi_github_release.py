"""Real package bytes with explicitly synthetic GitHub HTTPS responses."""
import hashlib
import asyncio
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'linux/arm64'))
from browser_update import BrowserUpdater,SOURCE,UpdateError
from github_release import API,DOWNLOAD,GitHubReleases,safe_url

class Response(io.BytesIO):
    def __init__(self,raw,url):
        super().__init__(raw);self.url=url;self.headers={'Content-Length':str(len(raw))}
    def geturl(self):return self.url

class Opener:
    def __init__(self,values):self.values=values;self.calls=[]
    def open(self,request,timeout):
        self.calls.append(request.full_url)
        value=self.values[request.full_url]
        if isinstance(value,Exception):raise value
        if not isinstance(value,bytes):value=json.dumps(value).encode()
        return Response(value,request.full_url)

def package(version='pi417-next',vm=417,caps=None,commit='2'*40):
    binary=bytearray(80);binary[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',binary,18,183)
    metadata={'version':version,'vm_version':vm,'source_commit':SOURCE,'architecture':'linux-aarch64',
        'capabilities':['python-extensions'] if caps is None else caps,'binary_sha256':hashlib.sha256(binary).hexdigest()}
    if commit is not None:metadata['provenance']={'port_commit':commit}
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as archive:
        for name,raw in [('smallvm',binary),('LICENSE',b'fixture'),('manifest.json',json.dumps(metadata).encode())]:
            info=tarfile.TarInfo(name);info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
    raw=output.getvalue();return raw,hashlib.sha256(raw).hexdigest(),metadata

@unittest.skipUnless(sys.platform=='linux','Managed Linux package review filesystem')
class GitHubTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config={'vm_version':417,'binary_sha256':'0'*64,'native_port_commit':'1'*40,'required_runtime_capabilities':['python-extensions']}
        self.save_config();self.updater=BrowserUpdater(self.root,'/not-executed',None,None)
    def tearDown(self):self.tmp.cleanup()
    def save_config(self):(self.root/'service.json').write_text(json.dumps(self.config))
    def source(self,*,status='ahead',preview=False,raw=None,digest=None):
        data,sha,metadata=package()
        if raw is not None:data=raw
        tag=metadata['version'];name='smallvm-linux-arm64-'+tag+'.tar.gz'
        release={'id':11,'tag_name':tag,'published_at':'2026-11-03T12:00:00Z','prerelease':preview,'draft':False,
            'assets':[{'id':22,'name':name,'size':len(data),'digest':'sha256:'+(digest or hashlib.sha256(data).hexdigest()),'browser_download_url':DOWNLOAD+tag+'/'+name}]}
        values={API+'/releases?per_page=30&page=1':[release],DOWNLOAD+tag+'/'+name:data,
            API+'/compare/'+'1'*40+'...'+'2'*40+'?per_page=1':{'status':status,'merge_base_commit':{'sha':'1'*40}}}
        opener=Opener(values);source=GitHubReleases(self.updater,opener);return source,opener,release,metadata
    def test_verified_latest_choice_only_stages_and_exposes_source(self):
        source,opener,release,metadata=self.source();progress=[]
        result=source.check(False,progress.append)
        self.assertEqual(result['choices'][0]['version'],'pi417-next')
        self.assertEqual(result['choices'][0]['repository'],'speccy88/microblocks-zephyr')
        selected=source.choose('11:22')
        self.assertEqual(selected['state'],'prepared');self.assertFalse(selected['native_install_enabled'])
        self.assertEqual(selected['port_commit'],'2'*40)
        self.assertFalse((self.root/'installed').exists())
        self.assertIn('github_downloading',[x['state'] for x in progress])
        state=json.loads((self.root/'updates/state.json').read_text())
        self.assertEqual(state['github']['baseline_binary_sha256'],'0'*64)
    def test_no_native_release_and_other_upstream_urls_are_not_offered(self):
        source,opener,release,_=self.source()
        release['assets'][0]['name']='smallvm-pi5-old.tar.gz'
        result=source.check(False,lambda x:None)
        self.assertEqual(result['choices'],[]);self.assertIn('Aucune version',result['message'])
        self.assertEqual(len(opener.calls),1)
    def test_preview_channel_is_explicit(self):
        source,_,_,_=self.source(preview=True)
        self.assertFalse(source.check(False,lambda x:None)['choices'])
        self.assertTrue(source.check(True,lambda x:None)['choices'][0]['prerelease'])
    def test_older_divergent_or_same_revision_rebuild_is_refused(self):
        for status in ('behind','diverged','identical'):
            with self.subTest(status=status):
                source,_,_,_=self.source(status=status)
                result=source.check(False,lambda x:None)
                self.assertFalse(result['choices']);self.assertIn('ancienne ou divergente',result['skipped'][0]['reason'])
        raw,_,_=package(commit='1'*40);source,_,_,_=self.source(raw=raw)
        self.assertIn('Même révision',source.check(False,lambda x:None)['skipped'][0]['reason'])
    def test_current_binary_is_up_to_date_without_install(self):
        source,opener,_,metadata=self.source();self.config['binary_sha256']=metadata['binary_sha256'];self.save_config()
        result=source.check(False,lambda x:None)
        self.assertTrue(result['up_to_date']);self.assertFalse(result['choices']);self.assertEqual(len(opener.calls),2)
    def test_missing_provenance_or_baseline_refuses_unordered_updates(self):
        raw,_,_=package(commit=None);source,_,_,_=self.source(raw=raw)
        self.assertIn('sans provenance',source.check(False,lambda x:None)['skipped'][0]['reason'])
        self.config.pop('native_port_commit');self.save_config();source,_,_,_=self.source()
        self.assertIn('installé inconnue',source.check(False,lambda x:None)['skipped'][0]['reason'])
    def test_corrupt_wrong_vm_and_missing_python_are_refused(self):
        variants=[(b'corrupt'+b'x'*100,None),(package(vm=421)[0],None),(package(caps=[])[0],None),(package()[0],'f'*64)]
        for raw,digest in variants:
            with self.subTest(digest=digest):
                source,_,_,_=self.source(raw=raw,digest=digest)
                self.assertFalse(source.check(False,lambda x:None)['choices'])
    def test_checksum_file_fallback_is_exact(self):
        source,opener,release,_=self.source();asset=release['assets'][0];digest=asset.pop('digest')[7:]
        release['assets'].append({'name':'SHA256SUMS','browser_download_url':DOWNLOAD+'pi417-next/SHA256SUMS'})
        opener.values[DOWNLOAD+'pi417-next/SHA256SUMS']=(digest+'  '+asset['name']+'\n').encode()
        self.assertTrue(source.check(False,lambda x:None)['choices'])
    def test_expired_or_changed_selection_cannot_be_prepared(self):
        source,_,_,_=self.source();source.check(False,lambda x:None)
        self.config['binary_sha256']='9'*64;self.save_config()
        with self.assertRaisesRegex(UpdateError,'a changé'):source.choose('11:22')
        timestamp,choice=source.choices['11:22'];source.choices['11:22']=(timestamp-601,choice)
        with self.assertRaisesRegex(UpdateError,'expirée'):source.choose('11:22')
    def test_changed_baseline_is_refused_again_before_apply(self):
        source,_,_,_=self.source();source.check(False,lambda x:None);selected=source.choose('11:22')
        self.updater.allow_apply=True;self.config['binary_sha256']='9'*64;self.save_config()
        async def send(value):raise AssertionError('Apply must not reach native validation')
        with self.assertRaisesRegex(UpdateError,'a changé'):
            asyncio.run(self.updater.apply(selected['sha256'],selected['version'],True,send))
    def test_github_rate_limit_and_catalog_bound_fail_explicitly(self):
        source,opener,release,_=self.source()
        opener.values[API+'/releases?per_page=30&page=1']=HTTPError(API,403,'limited',{},None)
        with self.assertRaisesRegex(UpdateError,'limite les requêtes'):source.check(False,lambda x:None)
        for page in range(1,4):opener.values[API+'/releases?per_page=30&page='+str(page)]=[release]*30
        with self.assertRaisesRegex(UpdateError,'trop grand'):source.check(False,lambda x:None)

class URLTests(unittest.TestCase):
    def test_only_verified_github_https_origins(self):
        for url in ['http://github.com/a','https://127.0.0.1/a','https://github.com.evil.invalid/a','https://user:pass@github.com/a','https://github.com:444/a','file:///tmp/package','https://github.com/a#fragment']:
            with self.subTest(url=url),self.assertRaises(UpdateError):safe_url(url)
        self.assertEqual(safe_url('https://release-assets.githubusercontent.com/path?token=opaque'),'https://release-assets.githubusercontent.com/path?token=opaque')

if __name__=='__main__':unittest.main()
