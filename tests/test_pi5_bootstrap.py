"""Archive/hash/launch boundaries; local fixtures, never install a service."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
script=(ROOT/'scripts/install-pi5.sh').read_text()
python=script.split("<<'PI5_BOOTSTRAP_PY'\n",1)[1].rsplit('\nPI5_BOOTSTRAP_PY',1)[0]
ns={'__name__':'bootstrap_under_test'};exec(compile(python,'install-pi5.sh','exec'),ns)

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.previous_umask=os.umask(0o077);os.umask(self.previous_umask)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.commit='a'*40;self.top='microblocks-zephyr-'+self.commit
    def tearDown(self):self.tmp.cleanup();os.umask(self.previous_umask)
    def archive(self,extra=None):
        target=self.root/('fixture'+str(len(list(self.root.iterdir())))+'.tar.gz')
        with tarfile.open(target,'w:gz') as out:
            item=tarfile.TarInfo(self.top+'/tools/install_pi5.py');raw=b'print("fixture installer")\n';item.size=len(raw);out.addfile(item,io.BytesIO(raw))
            if extra:out.addfile(extra,io.BytesIO(b'x'*extra.size) if extra.isfile() else None)
        return target
    def test_valid_archive_extracts_exact_source(self):
        root=ns['extract'](self.archive(),self.root/'out',self.commit)
        self.assertEqual(root.name,self.top);self.assertEqual((root/'tools/install_pi5.py').read_bytes(),b'print("fixture installer")\n')
    def test_traversal_links_wrong_root_and_duplicate_refused_before_write(self):
        entries=[]
        for name in ('../outside','/absolute',self.top+'/../outside','other-root/file',self.top+'/tools/install_pi5.py',self.top+'/bad\\file'):
            entries.append(tarfile.TarInfo(name))
        for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.FIFOTYPE):
            item=tarfile.TarInfo(self.top+'/link');item.type=kind;item.linkname='/etc/passwd';entries.append(item)
        for index,item in enumerate(entries):
            dest=self.root/('out'+str(index))
            with self.subTest(name=item.name,kind=item.type),self.assertRaises(RuntimeError):ns['extract'](self.archive(item),dest,self.commit)
            self.assertEqual(list(dest.iterdir()),[])
    def test_download_hash_checked_before_extraction(self):
        class Response(io.BytesIO):url='https://codeload.github.com/speccy88/microblocks-zephyr/tar.gz/commit'
        raw=b'fixture only';digest=hashlib.sha256(raw).hexdigest()
        self.assertEqual(ns['download']('https://github.com/archive',self.root/'valid',digest,opener=lambda *a,**kw:Response(raw)),len(raw))
        with self.assertRaisesRegex(RuntimeError,'nothing was extracted or executed'):
            ns['download']('https://github.com/archive',self.root/'bad','0'*64,opener=lambda *a,**kw:Response(raw))
    def test_download_destination_and_size_guard(self):
        class Response(io.BytesIO):url='http://unexpected.example/source'
        with self.assertRaises(RuntimeError):ns['download']('https://github.com/archive',self.root/'bad','0'*64,opener=lambda *a,**kw:Response(b'raw'))
        class Good(io.BytesIO):url='https://codeload.github.com/project/source'
        with patch.dict(ns,{'MAX_ARCHIVE':2}),self.assertRaises(RuntimeError):ns['download']('https://github.com/archive',self.root/'large','0'*64,opener=lambda *a,**kw:Good(b'too big'))
    def test_corrupt_download_never_executes_payload(self):
        with patch.object(ns['subprocess'],'run') as run,patch.dict(ns,{'download':lambda *a:(_ for _ in ()).throw(RuntimeError('bad hash'))}),patch.object(ns['os'],'geteuid',return_value=1000,create=True):
            with self.assertRaisesRegex(RuntimeError,'bad hash'):ns['main'](['--dry-run'])
            run.assert_not_called()
    def test_valid_download_forwards_arguments_and_source_marker(self):
        archive=self.archive();observed={}
        def download(url,target,digest):target.write_bytes(archive.read_bytes())
        def execute(args,**kw):
            payload=Path(args[3]);observed['args']=args;observed['marker']=json.loads((payload.parents[1]/'.pi5-bootstrap.json').read_text())
            return subprocess.CompletedProcess(args,0)
        with patch.dict(ns,{'download':download,'SOURCE_COMMIT':self.commit}),patch.object(ns['subprocess'],'run',side_effect=execute),patch.object(ns['os'],'geteuid',return_value=1000,create=True):
            self.assertEqual(ns['main'](['--prepare-only','--port','38877']),0)
        self.assertEqual(observed['args'][-3:],['--prepare-only','--port','38877']);self.assertEqual(observed['marker']['source_commit'],self.commit)
    def test_published_identity_has_real_pin_and_checksum(self):
        self.assertRegex(ns['SOURCE_COMMIT'],r'^[a-f0-9]{40}$');self.assertRegex(ns['SOURCE_SHA256'],r'^[a-f0-9]{64}$')
        self.assertEqual(ns['SOURCE_URL'],'https://github.com/speccy88/microblocks-zephyr/archive/'+ns['SOURCE_COMMIT']+'.tar.gz')

if __name__=='__main__':unittest.main()
