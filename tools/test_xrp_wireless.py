#!/usr/bin/env python3
"""Physical XRP WebSocket/HTTP acceptance using only vacant, owned test chunks.

No firmware update, Wi-Fi credentials, actuator writes or delete-all messages.
USB preemption is checked against the required exact XRP identity. HTTP assets
are compared with the verified installed image's generated asset manifest.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,concurrent.futures,gzip,hashlib,http.client,json,threading,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import websocket
from test_wireless_vm import VM,op,words,primitive
from test_generic_io import code_call
from xrp_serial import XRPSerialVM

class XRPWirelessVM(VM):
    all_crcs=XRPSerialVM.all_crcs
    def __init__(self,host):
        super().__init__(host)
        try:
            start=len(self.events);self.short(12)
            version=self.wait(lambda e:e[:2]==(22,0),after=start)[2].decode('utf8').lstrip('\x02')
            if version!='v417 XRP RP2350 Zephyr (actuators locked)':
                raise RuntimeError('Expected locked production XRP SmallVM')
            self.version=version
        except BaseException:self.close();raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True);p.add_argument('--port',required=True)
    p.add_argument('--usb-serial',required=True);p.add_argument('--assets',required=True,type=Path)
    p.add_argument('--source-commit',required=True);p.add_argument('--evidence',required=True,type=Path)
    args=p.parse_args()
    # Accept a literal IPv4 address only; no credential-bearing URLs or hosts.
    import ipaddress
    ipaddress.IPv4Address(args.host)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
        host=args.host,source_commit=args.source_commit,checks={},actuator_commands_sent=False,
        motor_supply_enabled=False,credentials_logged=False,scope='Physical XRP; native same-origin HTTP and binary WebSocket')
    vm=None;usb=None;original=None;owned={};audit=None
    local=threading.local();http_connections=[]
    report['http_asset_mode']='HTTP/1.1 keep-alive, two concurrent connections'
    def save():args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    def sync(n):
        start=len(vm.events);vm.short(26,n);vm.wait(lambda e:e[:2]==(26,n),after=start)
    def run(code):owned[224]=vm.upload(224,code,2);return vm.run_reporter(224)
    def rejected(origin):
        ws=None
        try:
            ws=websocket.create_connection('ws://'+args.host+'/ws/vm',origin=origin,timeout=3,http_no_proxy=['*'])
            answer=ws.recv()
            assert answer!='ready','Unexpected controller admission'
            return True
        except (OSError,websocket.WebSocketException):return True
        finally:
            if ws:ws.close()
    def asset_check(item):
        r=dict(path=item['path'],result='FAIL');started=time.monotonic()
        try:
            if not getattr(local,'connection',None):
                local.connection=http.client.HTTPConnection(args.host,timeout=30)
                http_connections.append(local.connection)
            local.connection.request('GET',urllib.parse.quote(item['path']),headers={'Accept-Encoding':'gzip','Connection':'keep-alive','User-Agent':'XRP-physical-asset-audit'})
            with local.connection.getresponse() as response:
                raw=response.read(item['flash_bytes']+1);headers=response.headers
                r['http_status']=response.status;r['received_bytes']=len(raw)
                assert response.status==200,'HTTP status '+str(response.status)
                assert len(raw)==item['flash_bytes'],'Incomplete body'
                assert hashlib.sha256(raw).hexdigest()==item['flash_sha256'],'Flash body hash'
                assert headers.get('Content-Encoding','')==item['encoding']
                assert headers.get('Content-Type','').split(';')[0]==item['content_type']
                assert headers.get('Cross-Origin-Opener-Policy')=='same-origin'
                assert headers.get('Cross-Origin-Embedder-Policy')=='require-corp'
                data=gzip.decompress(raw) if item['encoding']=='gzip' else raw
                assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
            r.update(result='PASS',bytes=len(raw),sha256=hashlib.sha256(data).hexdigest())
        except Exception as exc:
            r.update(error_type=type(exc).__name__,error=str(exc))
            if getattr(local,'connection',None):local.connection.close();local.connection=None
        r['seconds']=round(time.monotonic()-started,3)
        return r
    try:
        status=json.loads(opener.open('http://'+args.host+'/api/status',timeout=5).read())
        assert status['board']=='xrp-rp2350' and status['state']=='connected' and status['actuators_enabled'] is False
        assert status.get('radio_pm')==0,'Expected measured awake radio policy'
        report['checks']['http_status']=status
        assert rejected('http://invalid.example');report['checks']['cross_origin_rejected']=True
        vm=XRPWirelessVM(args.host);report['version']=vm.version;sync(91)
        original=vm.all_crcs();assert not set(original)&set(range(220,225)),'Preserve occupied test slots'
        report['checks']['original_code_crc32']={str(k):f'{v:08x}' for k,v in original.items()}
        assert rejected('http://'+args.host);report['checks']['second_controller_rejected']=True
        reporter=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
        owned[220]=vm.upload(220,reporter,2)
        assert [vm.run_reporter(220) for _ in range(10)]==[12]*10
        edited=bytearray(reporter);edited[5]=17
        owned[220]=vm.upload(220,edited,2);assert vm.run_reporter(220)==13
        owned[220]=vm.upload(220,reporter,2)
        report['checks'].update(arithmetic_runs=10,live_edit_result=13)
        # Audit two concurrent HTTP streams while the live VM produces output.
        items=json.loads(args.assets.read_text())['assets']
        audit=concurrent.futures.ThreadPoolExecutor(max_workers=2)
        futures=[audit.submit(asset_check,item) for item in items]
        stream=words([op(2,1),op(7,0),op(3,99),0,op(7,1),op(6,1),op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
        owned[221]=vm.upload(221,stream)
        start=len(vm.events);vm.short(3,221);vm.wait(lambda e:e[:2]==(17,221),seconds=25,after=start)
        outputs=[int(e[2][1:]) for e in vm.events[start:] if e[:2]==(20,254)]
        assert outputs==list(range(1,51));report['checks']['ordered_outputs']=outputs;save()
        large=words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0])
        owned[222]=vm.upload(222,large,fragmented=True)
        start=len(vm.events);vm.short(3,222);vm.wait(lambda e:e[:2]==(17,222),after=start)
        assert vm.variable(2)==42;report['checks']['fragmented_upload_bytes']=len(large)+7
        vm.ws.send_binary(bytes([251,32,7,100,0,1]));time.sleep(.35);sync(94)
        report['checks']['partial_frame_timeout_recovery']=True
        loop=words([op(9),op(2,3),op(8,5),op(22,-3)])
        owned[223]=vm.upload(223,loop);start=len(vm.events);vm.short(3,223)
        vm.wait(lambda e:e[:2]==(16,223),after=start);time.sleep(.1)
        vm.short(4,223);value=vm.variable(5);time.sleep(.15);assert value>0 and vm.variable(5)==value
        report['checks']['stop_and_variable_inspection']=True
        assert run(code_call(96,[0x6b,0x0f]))==108
        report['checks']['imu_id_over_wifi']=108
        samples={str(pin):run(code_call(86,[pin])) for pin in range(40,47)}
        assert all(type(v)==int and 0<=v<=1023 for v in samples.values())
        report['checks']['adc_over_wifi']=samples
        report['checks']['io_capabilities']=json.loads(run(primitive('ioCapabilities')))
        until=time.monotonic()+300
        while not all(f.done() for f in futures):
            if time.monotonic()>until:raise TimeoutError('Bounded full asset audit exceeded five minutes')
            vm.pump()
        assets=[f.result() for f in futures];audit.shutdown();audit=None
        report['checks']['assets']=dict(files=len(assets),bytes=sum(x.get('bytes',0) for x in assets),
            result='PASS' if all(x['result']=='PASS' for x in assets) else 'FAIL',assets=assets)
        assert all(x['result']=='PASS' for x in assets),'One or more HTTP assets failed'
        save();vm.close();vm=None;time.sleep(.2)
        vm=XRPWirelessVM(args.host);assert vm.run_reporter(220)==12
        report['checks']['wireless_reconnect_arithmetic']=12
        usb=XRPSerialVM(args.port,args.usb_serial);assert usb.run_reporter(220)==12
        vm.ws.settimeout(3)
        try:closed=vm.ws.recv() in ('',b'')
        except (OSError,websocket.WebSocketConnectionClosedException):closed=True
        assert closed,'Wireless controller did not yield to USB'
        report['checks']['identified_usb_preempts_wireless']=True
        vm.close();vm=None;usb.close();usb=None;time.sleep(.2)
        vm=XRPWirelessVM(args.host);assert vm.run_reporter(220)==12
        report['checks']['wireless_reconnect_after_usb']=12
        current=vm.all_crcs();assert current=={**original,**owned}
        for chunk in owned:vm.short(4,chunk);vm.short(2,chunk)
        sync(98);assert vm.all_crcs()==original;owned={}
        end=time.monotonic()+6
        while time.monotonic()<end:vm.pump()
        report['checks']['owned_test_chunks_removed_original_preserved']=True
        report['result']='PASS'
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        if audit:audit.shutdown(wait=False,cancel_futures=True)
        for connection in http_connections:connection.close()
        if vm:vm.close()
        if usb:usb.close()
        report['owned_test_crcs_remaining']={str(k):f'{v:08x}' for k,v in owned.items()}
        save();print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))

if __name__=='__main__':main()
