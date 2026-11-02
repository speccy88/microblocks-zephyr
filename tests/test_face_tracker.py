"""No device/model required: strict features and labelled simulated input."""
import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from face_tracker import FaceSample,demo_samples,eye_state,look_direction
class FaceTests(unittest.TestCase):
    def test_face_wire_is_independent_from_body_pose(self):
        packet=FaceSample(True,123,987,1,2,3,1).packet(0xffffffff)
        self.assertEqual(packet[:5],bytes((251,212,0,21,0)))
        self.assertEqual(struct.unpack('<4sBBBBIHHBBH',packet[5:-1]),(b'P4FC',1,1,1,2,0xffffffff,123,987,3,1,0))
        self.assertEqual(len(packet),26)
    def test_uncertain_lids_are_unknown(self):
        self.assertEqual([eye_state(v) for v in (0,.25,.4,.6,1)],[1,1,0,2,2])
    def test_estimated_eye_direction(self):
        self.assertEqual(look_direction({}),2)
        self.assertEqual(look_direction({'eyeLookOutLeft':.9,'eyeLookInRight':.8}),1)
        self.assertEqual(look_direction({'eyeLookInLeft':.9,'eyeLookOutRight':.8}),3)
    def test_demo_idle_wake_occlusion_and_departure(self):
        self.assertFalse(demo_samples(13)[0].visible)
        self.assertTrue(demo_samples(14)[0].visible)
        self.assertFalse(demo_samples(20.3)[0].visible)
        self.assertTrue(demo_samples(21)[0].visible)
        self.assertFalse(demo_samples(28)[0].visible)
        self.assertEqual(demo_samples(36),demo_samples(0))
        self.assertEqual({demo_samples(t/10)[1].gesture for t in range(140,280)},set(range(6)))
if __name__=='__main__':unittest.main()
