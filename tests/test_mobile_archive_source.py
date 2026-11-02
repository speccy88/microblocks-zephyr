"""Verified preview omits its raw entry; recover only the exact pinned template."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mobile_editor_source as source

class ReviewedSourceTests(unittest.TestCase):
    def test_preview_without_raw_entry_uses_pinned_template_and_rejects_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=root/'manifest.json';archive=root/'source.zip'
            (root/'dependencies').mkdir();(root/'dependencies/js-preview-site.json').write_text('{}')
            (root/'web/mobile').mkdir(parents=True);template=root/'web/mobile/purejs-source.html';template.write_bytes(b'<html>reviewed entry</html>')
            raw=template.read_bytes();engine=b'// reviewed engine'
            value={'files':[{'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in [('purejs.html',raw),('engine/fixture.js',engine)]]}
            manifest.write_text(json.dumps(value))
            with zipfile.ZipFile(archive,'w') as out:out.writestr('js-preview/waveshare/engine/fixture.js',engine)
            with patch.object(source,'ROOT',root),patch.object(source,'MANIFEST',manifest),patch.object(source,'config',return_value={}),patch.object(source,'reviewed_archive'),patch.object(source,'load_manifest',return_value=value):
                source.prepare_archive(archive,root/'output')
                self.assertEqual(source.read_editor(root/'output')['purejs.html'],raw)
                template.write_bytes(b'<html>modified</html>')
                with self.assertRaisesRegex(ValueError,'hash mismatch'):source.prepare_archive(archive,root/'bad-output')

if __name__=='__main__':unittest.main()
