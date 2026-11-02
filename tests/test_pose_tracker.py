"""Behavioral COCO tracker/gesture/host-wire tests, no model or device access."""
# SPDX-License-Identifier: MIT
import importlib.util
import math
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from pose_tracker import Tracker,Sample,FrameMux


def person(left=(.4,.7),right=(.6,.7),nose=(.5,.3),score=.9,box=(.25,.1,.75,.95)):
    points=[[0.,0.,0.] for _ in range(17)]
    points[0]=[*nose,.9];points[5]=[.4,.5,.9];points[6]=[.6,.5,.9]
    if left is not None:points[9]=[*left,.9]
    if right is not None:points[10]=[*right,.9]
    return dict(box=list(box),confidence=score,keypoints=points)


class PoseTrackerTests(unittest.TestCase):
    def settled(self,tracker,p):
        tracker.update([p],0)
        return tracker.update([p],.30)

    def test_neutral_and_anatomical_hands(self):
        for left,right,expected in [((.4,.7),(.6,.7),0),((.4,.2),(.6,.7),1),
                                    ((.4,.7),(.6,.2),2),((.4,.2),(.6,.2),3),
                                    ((.1,.5),(.9,.5),4),(None,None,0)]:
            with self.subTest(expected=expected):
                s=self.settled(Tracker(),person(left,right))
                self.assertTrue(s.visible);self.assertEqual(s.gesture,expected)

    def test_low_confidence_joint_cannot_raise_hand(self):
        p=person((.4,.1));p['keypoints'][9][2]=.1
        self.assertEqual(self.settled(Tracker(),p).gesture,0)

    def test_debounce_rejects_short_gesture(self):
        t=Tracker();t.update([person()],0)
        self.assertEqual(t.update([person((.4,.1))],.1).gesture,0)
        self.assertEqual(t.update([person()],.2).gesture,0)

    def test_wave_requires_reversals_and_raised_wrist(self):
        t=Tracker(debounce=0)
        result=None
        for i,x in enumerate([.3,.5,.3,.5,.3,.5]):
            result=t.update([person((x,.2))],i*.15)
        self.assertEqual(result.gesture,5)
        self.assertEqual(t.update([person()],1).gesture,0)

    def test_missing_or_invalid_keypoints_reject_person(self):
        for value in [float('nan'),float('inf'),-1,2]:
            p=person();p['keypoints'][0][0]=value
            self.assertFalse(Tracker().update([p],0).visible)
        p=person();p['keypoints']=[]
        self.assertFalse(Tracker().update([p],0).visible)

    def test_no_nose_falls_back_to_confident_shoulders(self):
        p=person();p['keypoints'][0][2]=0
        self.assertEqual(Tracker().update([p],0).y,500)
        p['keypoints'][5][2]=0
        self.assertFalse(Tracker().update([p],0).visible)

    def test_mirror_and_smoothing(self):
        p=person(nose=(.2,.3));t=Tracker(mirror=True)
        self.assertEqual(t.update([p],0).x,800)
        moved=t.update([person(nose=(.8,.3))],.02)
        self.assertGreater(moved.x,200);self.assertLess(moved.x,800)

    def test_identity_hold_and_reacquisition(self):
        t=Tracker();first=person(nose=(.2,.3),box=(.05,.1,.35,.9))
        second=person(nose=(.85,.3),box=(.7,.1,1.,.9))
        self.assertEqual(t.update([first],0).x,200)
        self.assertFalse(t.update([second],.2).visible)
        self.assertEqual(t.update([second],1.0).x,850)

    def test_loss_resets_gestures_and_long_gap_resets_gaze(self):
        t=Tracker();self.assertEqual(self.settled(t,person((.4,.1))).gesture,1)
        self.assertEqual(t.update([], .4),Sample())
        self.assertEqual(t.update([person(nose=(.8,.3))],2).x,800)

    def test_packet_exact_format_and_wrapping(self):
        packet=Sample(True,123,456,900,3).packet(0x100000001)
        self.assertEqual(packet[:5],bytes([251,210,0,21,0]));self.assertEqual(packet[-1],254)
        self.assertEqual(struct.unpack('<4sBBBBIHHHH',packet[5:-1]),(b'P4PS',1,1,3,0,1,123,456,900,0))
        self.assertEqual(len(packet),26)

    def test_model_and_camera_imports_are_explicit(self):
        before=set(sys.modules)
        import pose_eyes
        self.assertNotIn('ultralytics',set(sys.modules)-before)
        self.assertNotIn('serial',set(sys.modules)-before)
        with self.assertRaises(ValueError):pose_eyes.source_value('https://camera.invalid/feed')

    def test_pose_never_splits_fragmented_editor_upload(self):
        sent=[];mux=FrameMux(sent.append);upload=b'\xfb\x20\x0a\x06\x00abcdef'
        for b in upload[:-1]:
            mux.feed(bytes([b]));self.assertFalse(mux.inject(Sample().packet(1)))
        mux.feed(upload[-1:]);self.assertEqual(sent,[upload])
        self.assertTrue(mux.inject(Sample().packet(2)))
        mux.feed(b'\xfa\x1a\x49\xfa\x0c\x00')
        self.assertEqual(sent[-2:],[b'\xfa\x1a\x49',b'\xfa\x0c\x00'])

    def test_mux_rejects_unbounded_or_unframed_data(self):
        for data in [b'hello',b'\xfb\x20\x00\xff\xff',b'x'*16385]:
            with self.assertRaises(ValueError):FrameMux(lambda _:None).feed(data)

    def test_p4_interval_can_debounce_sustained_raised_hand(self):
        t=Tracker(max_gap=3,wave_window=4)
        self.assertEqual(t.update([person((.4,.2))],0).gesture,0)
        self.assertEqual(t.update([person((.4,.2))],1.2).gesture,1)
        self.assertEqual(t.update([],1.3),Sample())

    def test_oled_address_aliases_are_write_addresses_only(self):
        import pose_eyes
        self.assertEqual(pose_eyes.oled_address('auto'),0)
        for value,expected in [('0x78',60),('0x7a',61),('0x3c',60),('61',61)]:
            self.assertEqual(pose_eyes.oled_address(value),expected)
        for value in ['0x79','0x7b','0x18','128','bad']:
            with self.assertRaises(Exception):pose_eyes.oled_address(value)

    @unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('cv2'),'Optional image dependencies unavailable')
    def test_gray4_decode_and_p4_capture_cleanup(self):
        import pose_eyes
        self.assertEqual(pose_eyes.unpack_gray4(bytes([0x08,0xf0]),3,1).tolist(),[[0,136,255]])
        with self.assertRaises(ValueError):pose_eyes.unpack_gray4(b'',160,90)
        class FakeVM:
            def __init__(self,truncated=False):self.calls=[];self.requests=[];self.truncated=truncated
            def call(self,name,*args):
                self.calls.append((name,args))
                return {'cameraRequest':True,'cameraBusy':False,'cameraResult':11,'imageResize':22,'imageRelease':True,'imageReleaseAll':True}[name]
            def image_request(self,operation,handle,offset,count):
                self.requests.append((operation,handle,offset,count))
                return b'\x0f'*(count-1 if self.truncated else count)
        vm=FakeVM();frame,captured=pose_eyes.p4_frame(vm)
        self.assertEqual(frame.shape,(108,192,3));self.assertGreater(captured,0)
        self.assertEqual(sum(r[3] for r in vm.requests),10368)
        self.assertTrue(all(r[0]==3 and r[1]==22 and r[3]<=512 for r in vm.requests))
        self.assertEqual(vm.calls[-1],('imageReleaseAll',()))
        vm=FakeVM(True)
        with self.assertRaises(RuntimeError):pose_eyes.p4_frame(vm)
        self.assertEqual(vm.calls[-1],('imageReleaseAll',()))


if __name__=='__main__':unittest.main()
