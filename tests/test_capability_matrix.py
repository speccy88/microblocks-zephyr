"""Capability claims must preserve provenance and target/test distinctions."""
import copy
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import capability_matrix as matrix

class CapabilityMatrixTests(unittest.TestCase):
    def setUp(self):self.value=matrix.load()
    def test_generated_document_and_camera_unknowns_are_preserved(self):
        self.assertEqual((ROOT/'docs/CAPABILITY_MATRIX.md').read_text(encoding='utf-8'),matrix.render(self.value))
        targets={t['id']:t for t in self.value['targets']}
        self.assertIsNone(targets['microduck']['camera']['capture_resolutions'])
        self.assertFalse(targets['microduck']['camera']['capture'])
        self.assertEqual(targets['microduck']['features']['sensors']['validation'],'simulation')
        self.assertEqual(targets['raspberry-pi5']['features']['sensors']['validation'],'software_only')
        self.assertEqual(targets['waveshare-p4']['features']['camera_capture']['validation'],'physical_limited')
    def test_physical_claim_cannot_be_inherited_by_planned_cpu_or_simulator(self):
        value=copy.deepcopy(self.value);target=next(t for t in value['targets'] if t['id']=='linux-arm32')
        target['features']['sqlite']=copy.deepcopy(next(t for t in value['targets'] if t['id']=='raspberry-pi5')['features']['sqlite'])
        with self.assertRaises(ValueError):matrix.validate(value)
        value=copy.deepcopy(self.value);target=next(t for t in value['targets'] if t['id']=='microduck');target['features']['sensors']['validation']='physical_target'
        with self.assertRaises(ValueError):matrix.validate(value)
    def test_missing_evidence_changed_manifest_and_unknown_feature_fail(self):
        for mutate in [lambda v:v['targets'][0]['sources'].append('not-a-source.json'),
                       lambda v:v['targets'][0]['reviewed_source_hashes'].update({next(iter(v['targets'][0]['reviewed_source_hashes'])):'0'*64}),
                       lambda v:v['targets'][0]['features'].update({'invented_feature':{}})]:
            value=copy.deepcopy(self.value);mutate(value)
            with self.assertRaises(ValueError):matrix.validate(value)

if __name__=='__main__':unittest.main()
