#!/usr/bin/env python3
"""User-controlled Windows vault -> exact identified XRP, MBNW v2.

Only the local Connect click reads the reusable vault entry and sends a key.
--probe/--self-test do not read a credential or join. Persistence is opt-in.
The deployment country must already be selected in the installed image.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,json,queue,secrets,threading,time
from datetime import datetime,timezone
from pathlib import Path
from xrp_serial import XRPSerialVM
from network_setup_client import encode

def wipe(data): data[:]=b'\0'*len(data)

class SetupClient:
    def __init__(self,port,usb_serial):
        self.vm=XRPSerialVM(port,usb_serial);self.payload_written=False
    def request(self,op,ssid=None,key=None,remember=False):
        ident=secrets.randbits(32) or 1;packet=encode(op,ident,ssid,key,remember)
        start=len(self.vm.events)
        try:
            self.vm.send(packet)
            if op==2:self.payload_written=True
        finally:wipe(packet)
        def matching(e):
            if e[:2]!=(205,0) or len(e[2])>640:return False
            try:return json.loads(e[2]).get('request')==ident
            except (ValueError,AttributeError):return False
        reply=json.loads(self.vm.wait(matching,after=start)[2])
        if type(reply.get('accepted')) is not bool or not isinstance(reply.get('status'),dict):
            raise RuntimeError('Invalid setup response')
        return reply
    def probe(self):
        r=self.request(1);s=r['status']
        if not r['accepted'] or s.get('board')!='xrp-rp2350' or s.get('setup_protocol')!=2:
            raise RuntimeError('Expected XRP MBNW v2 firmware')
        return r
    def close(self):self.vm.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True);p.add_argument('--usb-serial',required=True)
    p.add_argument('--country',required=True,help='Deployment country already selected in the installed firmware')
    p.add_argument('--probe',action='store_true');p.add_argument('--self-test',action='store_true')
    p.add_argument('--receipt',type=Path,default=Path(__file__).resolve().parents[2]/'.private/xrp-install-2026-10-19/wifi-status.json')
    args=p.parse_args()
    if args.self_test:
        packet=encode(2,123,bytearray(b'Test'),bytearray(b'unit-key'),True)
        assert packet[:5]==bytes([251,205,0,26,0]) and packet[15:18]==bytes([1,4,8])
        wipe(packet);assert not any(packet)
        print('PASS: XRP v2 fixture and wiping only; no USB/vault/network access');return
    if args.probe:
        c=SetupClient(args.port,args.usb_serial)
        try:print(json.dumps(c.probe(),indent=2))
        finally:c.close()
        return
    import tkinter as tk
    from tkinter import ttk
    root=tk.Tk();root.title('XRP — connexion Wi-Fi');root.geometry('820x490')
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Connecter ce XRP au Wi-Fi du coffre Windows',font=('Segoe UI',15,'bold')).pack(anchor='w')
    ttk.Label(frame,wraplength=765,justify='left',text=
        f'Cible : XRP USB {args.port} — {args.usb_serial}.\nPays configuré : {args.country}.\n'
        'Le mot de passe sera lu uniquement lors de ton clic et envoyé à cette carte par USB.\n'
        'Il ne passe ni par le chat, ni par le navigateur, ni par les programmes MicroBlocks.').pack(anchor='w',pady=16)
    remember=tk.BooleanVar(value=False)
    check=ttk.Checkbutton(frame,text='Mémoriser ce réseau sur le XRP pour les prochains démarrages',variable=remember)
    check.pack(anchor='w')
    status=tk.StringVar(value='Prêt. Aucun mot de passe n’a été lu ou envoyé.')
    ttk.Label(frame,textvariable=status,wraplength=760,justify='left').pack(anchor='w',pady=20)
    events=queue.Queue();running=False
    def worker(save):
        c=None;ssid=None;key=None
        receipt=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
            user_clicked_connect=True,target_usb_serial=args.usb_serial,target_port=args.port,
            country=args.country,remember_requested=save,credential_values_logged=False,
            credential_payload_written=False,programs_unchanged=False)
        try:
            c=SetupClient(args.port,args.usb_serial);probe=c.probe()['status']
            if not probe.get('radio_ready'):raise RuntimeError('RM2 driver is not ready; no vault read performed')
            if save and not probe.get('persistence_supported'):raise RuntimeError('Persistence unavailable; no vault read performed')
            before=c.vm.all_crcs()
            # This reviewed reader does no USB I/O. Its only invocation is
            # here, in the target-specific worker started by the user's click.
            from provision_fruit_jam_wifi import read_selected_vault_for_user_action
            ssid,key=read_selected_vault_for_user_action()
            events.put(('status','Connexion au réseau enregistré…'))
            reply=c.request(2,ssid,key,save);receipt['credential_payload_written']=c.payload_written
            wipe(ssid);wipe(key);ssid=key=None
            if not reply['accepted']:raise RuntimeError('Board rejected setup: '+str(reply.get('command_error')))
            until=time.monotonic()+70
            while time.monotonic()<until:
                reply=c.request(3);s=reply['status']
                if not s.get('busy') and s.get('state')=='connected':break
                if not s.get('busy') and s.get('state') not in ('joining','dhcp'):
                    raise RuntimeError('Connection failed: '+str(s.get('error')))
                end=time.monotonic()+.4
                while time.monotonic()<end:c.vm.pump()
            else:raise RuntimeError('Connection timeout')
            if s.get('ip') in (None,'','0.0.0.0'):raise RuntimeError('No DHCP address')
            receipt.update(result='PASS',association_verified=True,dhcp_verified=True,
                ip=s['ip'],programs_unchanged=c.vm.all_crcs()==before)
            if not receipt['programs_unchanged']:raise RuntimeError('VM program CRCs changed')
            events.put(('status','Connecté — adresse IP : '+s['ip']+('. Réseau mémorisé.' if save else '. Réseau non mémorisé.')))
        except Exception as exc:
            receipt['result']='FAIL';receipt['error_type']=type(exc).__name__
            events.put(('status','Échec : '+str(exc)))
        finally:
            if ssid is not None:wipe(ssid)
            if key is not None:wipe(key)
            if c:c.close()
            args.receipt.parent.mkdir(parents=True,exist_ok=True)
            args.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8',newline='\n')
            events.put(('done',None))
    def click():
        nonlocal running
        if running:return
        running=True;button.configure(state='disabled');check.configure(state='disabled')
        threading.Thread(target=worker,args=(remember.get(),),daemon=True).start()
    button=ttk.Button(frame,text='Connecter ce XRP avec le Wi-Fi du coffre Windows',command=click)
    button.pack(anchor='w',pady=10)
    def poll():
        nonlocal running
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='status':status.set(value)
                else:running=False;button.configure(state='normal');check.configure(state='normal')
        except queue.Empty:pass
        root.after(100,poll)
    poll();root.mainloop()

if __name__=='__main__':main()
