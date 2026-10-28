"""Static publication gate fixtures; no download, deployment or hardware."""
# SPDX-License-Identifier: MIT
import hashlib,importlib.util,json,pathlib,stat,struct,tempfile,unittest,urllib.request,warnings,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('preview_asset',ROOT/'tools/add_js_preview.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class PublicationGate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='publication-fixture-');self.root=pathlib.Path(self.temp.name);self.gp=self.root/'gp';self.gp.mkdir()
        (self.gp/'index.html').write_bytes(b'GP unchanged');(self.gp/'linux-preview-manifest.json').write_bytes(b'{}')
        self.original=p.files(self.gp)
    def tearDown(self):self.temp.cleanup()
    def archive(self,extra=None,symlink=False,corrupt=False):
        data={'index.html':b'GP unchanged','linux-preview-manifest.json':b'{}','js-preview/index.html':b'JS preview'}
        hashes={n:p.digest(b) for n,b in data.items()}
        site={'gp_files_preserved':self.original,'files':hashes,'runtime_upgraded':False,'upstream_engine_modified':False}
        raw=json.dumps(site).encode();data['js-preview/site-manifest.json']=raw
        if corrupt:data['js-preview/index.html']=b'tampered JS'
        if extra:data.update(extra)
        path=self.root/'test.zip'
        with zipfile.ZipFile(path,'w') as z:
            for n,b in data.items():
                item=zipfile.ZipInfo(n);item.external_attr=((stat.S_IFLNK|0o777) if symlink and n=='js-preview/index.html' else (stat.S_IFREG|0o644))<<16;z.writestr(item,b)
        m={'schema':1,'release_tag':'fixture','asset_url':'https://github.com/speccy88/microblocks-zephyr/releases/download/fixture/gp-with-js-preview-preserved.zip',
           'archive_bytes':path.stat().st_size,'archive_sha256':p.digest(path.read_bytes()),'gp_manifest_sha256':p.digest(b'{}'),
           'site_manifest_sha256':p.digest(raw),'gp_source_commit':'a'*40,'editor_source_commit':'b'*40,'file_count':len(data)}
        return path,m
    def test_adds_only_js_and_never_replaces_existing_gp_or_js(self):
        archive,m=self.archive();result=p.install(archive,self.gp,m)
        self.assertEqual(result['gp_files_preserved'],2);self.assertEqual((self.gp/'index.html').read_bytes(),b'GP unchanged')
        self.assertEqual((self.gp/'js-preview/index.html').read_bytes(),b'JS preview')
        with self.assertRaisesRegex(ValueError,'Fresh GP'):p.install(archive,self.gp,m)
    def test_traversal_and_nonregular_entries_fail_without_writes(self):
        for name in ('../escape','js-preview/../escape','/absolute','js-preview\\escape','js-preview/C:drive'):
            archive,m=self.archive({name:b'bad'})
            with self.assertRaises(ValueError):p.install(archive,self.gp,m)
            self.assertEqual(p.files(self.gp),self.original)
        archive,m=self.archive(symlink=True)
        with self.assertRaisesRegex(ValueError,'Non-regular'):p.install(archive,self.gp,m)
    def test_corrupt_unlisted_and_wrong_gp_snapshots_fail_closed(self):
        for options in ({'corrupt':True},{'extra':{'js-preview/unlisted.js':b'bad'}}):
            archive,m=self.archive(**options)
            with self.assertRaises(ValueError):p.install(archive,self.gp,m)
            self.assertEqual(p.files(self.gp),self.original)
        archive,m=self.archive();(self.gp/'index.html').write_bytes(b'GP new work')
        with self.assertRaisesRegex(ValueError,'preservation'):p.install(archive,self.gp,m)
        self.assertEqual((self.gp/'index.html').read_bytes(),b'GP new work')
    def test_hash_size_and_download_destination_are_exact(self):
        archive,m=self.archive()
        for changed in ({'archive_sha256':'0'*64},{'archive_bytes':1},{'file_count':1},{'site_manifest_sha256':'0'*64},{'asset_url':'http://example.invalid/asset'}):
            with self.assertRaises(ValueError):p.install(archive,self.gp,{**m,**changed})
        self.assertEqual(p.files(self.gp),self.original)
    def test_duplicate_and_oversized_headers_are_rejected_before_extraction(self):
        archive,m=self.archive()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(archive,'a') as z:z.writestr('js-preview/index.html',b'duplicate')
        m.update(archive_bytes=archive.stat().st_size,archive_sha256=p.digest(archive.read_bytes()),file_count=5)
        with self.assertRaisesRegex(ValueError,'Duplicate'):p.install(archive,self.gp,m)
        archive,m=self.archive();raw=bytearray(archive.read_bytes());offset=raw.index(b'PK\x01\x02');struct.pack_into('<I',raw,offset+24,32*1024*1024+1);archive.write_bytes(raw)
        m['archive_sha256']=p.digest(raw)
        with self.assertRaisesRegex(ValueError,'member bound'):p.install(archive,self.gp,m)
        self.assertEqual(p.files(self.gp),self.original)
    def test_download_redirect_cannot_downgrade_or_change_trust_domain(self):
        handler=p.GitHubHTTPS();request=urllib.request.Request('https://github.com/source')
        for url in ('http://github.com/asset','https://example.invalid/asset','https://github.com.example.invalid/asset','https://u:p@github.com/asset','https://github.com:444/asset'):
            with self.assertRaises(ValueError):handler.redirect_request(request,None,302,'redirect',{},url)
