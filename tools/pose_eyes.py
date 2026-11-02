#!/usr/bin/env python3
"""P4-attached camera -> local YOLO pose -> P4 eyes (default source: p4).

Use --dry-run for model/video testing without a board. For simultaneous GP
editing with an optional webcam use serve_p4_ide.py --pose-source 0.
--identify-oled probes only 0x3c/0x3d; an ACK cannot identify the controller.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
import os
from pathlib import Path
import threading
import time
from pose_tracker import Tracker, Sample, candidates, GESTURES
DEFAULT_MODEL=str(Path(__file__).resolve().parents[1]/'build-artifacts/pose/yolo11n-pose.pt')
P4_WIDTH,P4_HEIGHT=192,108


def load_model(path):
    # Isolate package preferences and disable optional upstream analytics before
    # inference. Private input frames never leave the local process.
    os.environ['YOLO_CONFIG_DIR']=str(Path(__file__).resolve().parents[1]/'build-artifacts/pose/settings')
    from ultralytics import YOLO,settings
    import torch
    settings.update({'sync':False})
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    model=YOLO(path)
    if model.task!='pose':
        raise ValueError('A COCO-17 pose model is required (for example yolo11n-pose.pt)')
    return model


def source_value(source):
    if source.isdecimal():return int(source)
    path=Path(source).resolve()
    if not path.is_file():raise ValueError('Source must be a camera number or existing local video/image')
    return str(path)


class PoseProducer:
    """One inference worker, one latest sample; never queues stale video."""
    def __init__(self,source,model=DEFAULT_MODEL,mirror=False):
        self.source,self.model_path,self.mirror=source,model,mirror
        self.stop=threading.Event();self.lock=threading.Lock()
        self.latest=None;self.error=None;self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self.run,name='local-yolo-pose',daemon=True)
        self.thread.start()

    def take(self):
        with self.lock:
            value=self.latest;self.latest=None
            return value

    def run(self):
        capture=None
        try:
            import cv2
            model=load_model(self.model_path);tracker=Tracker(mirror=self.mirror)
            if self.stop.is_set():return
            capture=cv2.VideoCapture(source_value(self.source))
            if not capture.isOpened():raise RuntimeError('Camera/video could not be opened')
            capture.set(cv2.CAP_PROP_BUFFERSIZE,1)
            while not self.stop.is_set():
                ok,frame=capture.read()
                if not ok:break
                began=time.monotonic()
                result=model.predict(frame,imgsz=320,conf=.5,verbose=False)[0]
                sample=tracker.update(candidates(result),began)
                with self.lock:self.latest=(began,sample)
                self.stop.wait(max(0,.10-(time.monotonic()-began)))
        except Exception as error:
            self.error=f'{type(error).__name__}: {error}'
        finally:
            if capture is not None:capture.release()
            with self.lock:self.latest=(time.monotonic(),Sample())


def call(vm,name,*args,primitive_set=3):
    from p4_serial import primitive
    vm.upload(10,primitive(name,args,primitive_set),2)
    return vm.run_reporter(10)


def oled_address(value):
    if value.lower()=='auto':return 0
    try:address=int(value,0)
    except ValueError as error:raise argparse.ArgumentTypeError('Use auto, 0x3c/0x3d, or write-address alias 0x78/0x7a') from error
    if address in (0x78,0x7a):address>>=1
    if address not in (0x3c,0x3d):raise argparse.ArgumentTypeError('OLED address must be 0x3c/0x3d (0x78/0x7a write aliases accepted)')
    return address


def identify_oled(vm):
    if not call(vm,'probe',primitive_set=26):raise RuntimeError('Stop eyes before probing; another OLED job may be active')
    deadline=time.monotonic()+3
    while call(vm,'probing',primitive_set=26):
        if time.monotonic()>deadline:raise TimeoutError('OLED probe deadline; camera/audio/discovery may own the bus')
        time.sleep(.02)
    address=call(vm,'address',primitive_set=26)
    return dict(address=address,address_hex=f'0x{address:02X}' if address>0 else None,
                controller='unconfirmed: SSD1306/SH1106 cannot be distinguished by address ACK',
                status=call(vm,'status',primitive_set=26))


def unpack_gray4(data,width=P4_WIDTH,height=P4_HEIGHT):
    import numpy as np
    pixels=width*height
    if width<=0 or height<=0 or len(data)!=(pixels+1)//2:raise ValueError('Incorrect packed grayscale frame length')
    packed=np.frombuffer(data,dtype=np.uint8)
    values=np.empty(len(packed)*2,dtype=np.uint8)
    values[0::2]=(packed>>4)*17;values[1::2]=(packed&15)*17
    return values[:pixels].reshape(height,width)


def p4_frame(vm):
    """Exclusive controller only: capture, bounded resize/export, always release."""
    import cv2
    try:
        if not vm.call('cameraRequest'):raise RuntimeError(vm.call('cameraStatus'))
        deadline=time.monotonic()+8
        while vm.call('cameraBusy'):
            if time.monotonic()>deadline:raise TimeoutError('P4 camera capture')
        captured=time.monotonic()
        handle=vm.call('cameraResult')
        if not handle:raise RuntimeError(vm.call('cameraStatus'))
        small=vm.call('imageResize',handle,P4_WIDTH,P4_HEIGHT)
        vm.call('imageRelease',handle)
        if not small:raise RuntimeError('P4 resize failed')
        # Operation 3 is bounded packed grayscale: 4x less than RGB565 export.
        raw=bytearray()
        packed_bytes=(P4_WIDTH*P4_HEIGHT+1)//2
        for offset in range(0,packed_bytes,512):
            count=min(512,packed_bytes-offset)
            chunk=vm.image_request(3,small,offset,count)
            if len(chunk)!=count:raise RuntimeError('Truncated P4 grayscale export')
            raw.extend(chunk)
        return cv2.cvtColor(unpack_gray4(raw),cv2.COLOR_GRAY2BGR),captured
    finally:
        vm.call('imageReleaseAll')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='p4',help='p4 (default, attached camera, exclusive USB), webcam number, or local video/image')
    p.add_argument('--model',default=DEFAULT_MODEL,help='COCO-17 pose weights; first use may download into ignored build-artifacts')
    p.add_argument('--mirror',action='store_true');p.add_argument('--preview',action='store_true')
    p.add_argument('--serial',action='store_true',help='Open COM5 only; close the editor first; stops running scripts and uses VM chunk 10')
    p.add_argument('--dry-run',action='store_true',help='Infer without any board access')
    p.add_argument('--frames',type=int,default=0,help='Stop after this many frames; 0 until EOF/Ctrl+C')
    p.add_argument('--controller',choices=['ssd1306','sh1106'],default='ssd1306')
    p.add_argument('--height',type=int,choices=[32,64],default=64)
    p.add_argument('--address',type=oled_address,default=0,help='auto (default), 0x3c/0x3d, or 0x78/0x7a write aliases')
    p.add_argument('--identify-oled',action='store_true',help='Address-only diagnostic over COM5; does not initialize OLED, capture camera, or load YOLO')
    p.add_argument('--alignment-test',action='store_true',help='Initialize selected profile and show edge/center pattern; no YOLO/camera; Ctrl+C exits')
    p.add_argument('--report',type=Path,help='Summary counts only; no frames, keypoints or identifiers')
    a=p.parse_args()
    if a.serial==a.dry_run:p.error('Choose exactly one of --serial or --dry-run')
    if a.source=='p4' and not a.serial:p.error('--source p4 requires --serial')
    if a.controller=='sh1106' and a.height!=64:p.error('SH1106 requires height 64')
    if a.frames<0:p.error('--frames must be nonnegative')
    if a.identify_oled or a.alignment_test:
        if not a.serial:p.error('OLED diagnostics require --serial')
        from p4_serial import P4SerialVM
        vm=P4SerialVM()
        try:
            diagnostic=identify_oled(vm);print(json.dumps(diagnostic,indent=2))
            if a.alignment_test:
                address=a.address or diagnostic['address']
                if address<=0:raise RuntimeError('No unique OLED address; select a responding address explicitly')
                if not call(vm,'begin',a.height,int(a.controller=='sh1106'),address,primitive_set=26):raise RuntimeError('OLED initialization rejected')
                call(vm,'alignment',True,primitive_set=26)
                print('Selected '+a.controller+' profile, not an identified chip. Compare all four borders and centered cross.',flush=True)
                while True:vm.pump();vm.events.clear();time.sleep(.05)
        except KeyboardInterrupt:pass
        finally:
            if a.alignment_test:call(vm,'stop',primitive_set=26)
            vm.close()
        return
    import cv2
    model=load_model(a.model)
    tracker=Tracker(mirror=a.mirror,max_gap=3 if a.source=='p4' else .75,wave_window=4 if a.source=='p4' else 1.3)
    capture=None;vm=None
    frames=visible=0;gestures=set();durations=[];sequence=0
    try:
        if a.serial:
            from p4_serial import P4SerialVM
            vm=P4SerialVM()
            vm.short(15) # Explicit exclusive-controller mode; stop existing tasks/captures.
            diagnostic=identify_oled(vm);print(json.dumps(diagnostic,indent=2))
            address=a.address or diagnostic['address']
            if address<=0:raise RuntimeError('No unique OLED address; check wiring or select a responding address explicitly')
            if not call(vm,'begin',a.height,int(a.controller=='sh1106'),address,primitive_set=26):raise RuntimeError('OLED initialization rejected')
            deadline=time.monotonic()+3
            while not call(vm,'ready',primitive_set=26):
                if time.monotonic()>deadline:raise RuntimeError(call(vm,'status',primitive_set=26))
                time.sleep(.02)
            print('Using '+a.controller+' controller profile; chip identity remains unconfirmed.',flush=True)
            call(vm,'follow',True,True,primitive_set=27)
        if a.source!='p4':
            capture=cv2.VideoCapture(source_value(a.source))
            if not capture.isOpened():raise RuntimeError('Camera/video could not be opened')
            capture.set(cv2.CAP_PROP_BUFFERSIZE,1)
        while not a.frames or frames<a.frames:
            frame=None;captured=None
            if a.source=='p4':frame,captured=p4_frame(vm)
            if capture is not None:
                ok,frame=capture.read()
                if not ok:break
            began=time.monotonic()
            if captured is None:captured=began
            result=model.predict(frame,imgsz=320,conf=.5,verbose=False)[0]
            sample=tracker.update(candidates(result),began)
            elapsed=time.monotonic()-began;durations.append(elapsed)
            # Do not renew the board's freshness lease with old inference.
            max_age=2 if a.source=='p4' else 1
            if time.monotonic()-captured>max_age:sample=Sample()
            sequence+=1
            if vm:
                vm.send(sample.packet(sequence));vm.pump();vm.events.clear()
            frames+=1;visible+=int(sample.visible);gestures.add(GESTURES[sample.gesture])
            if frames==1 or frames%30==0:print(json.dumps(dict(frame=frames,person=sample.visible,gesture=GESTURES[sample.gesture],inference_ms=round(elapsed*1000))),flush=True)
            if a.preview:
                cv2.imshow('Local YOLO pose (Q to quit)',result.plot())
                if cv2.waitKey(1)&255==ord('q'):break
            time.sleep(max(0,.10-elapsed))
    except KeyboardInterrupt:
        pass
    finally:
        if capture is not None:capture.release()
        if a.preview:cv2.destroyAllWindows()
        if vm:
            try:
                vm.send(Sample().packet(sequence+1));call(vm,'follow',False,False,primitive_set=27);call(vm,'stop',primitive_set=26)
            finally:vm.close()
    report=dict(frames=frames,frames_with_person=visible,gestures=sorted(gestures),
                mean_inference_ms=round(sum(durations)/len(durations)*1000,2) if durations else None,
                inference_location='computer',board_accessed=a.serial,physical_oled_verified=False)
    print(json.dumps(report,indent=2))
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
    if not frames:raise RuntimeError('No frames processed')


if __name__=='__main__':main()
