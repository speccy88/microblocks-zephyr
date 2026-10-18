#!/usr/bin/env python3
"""User-controlled Windows vault -> verified Fruit Jam Wi-Fi setup.

Default opens a local GUI. Only the user's Connect click can read the vault
and send a credential. --probe and --self-test never read a password or join.
No credentials in CLI arguments, HTTP, stdout, VM chunks or receipt files.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,ctypes,json,queue,threading,time
from ctypes import wintypes
from datetime import datetime,timezone
from pathlib import Path
from fruit_jam_wifi import SetupClient,encode_request,wipe

TARGET='Codex/Electronics/WiFi/Default'
class Credential(ctypes.Structure):
    _fields_=[('Flags',wintypes.DWORD),('Type',wintypes.DWORD),('TargetName',wintypes.LPWSTR),
      ('Comment',wintypes.LPWSTR),('LastWritten',wintypes.FILETIME),('CredentialBlobSize',wintypes.DWORD),
      ('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),('Persist',wintypes.DWORD),('AttributeCount',wintypes.DWORD),
      ('Attributes',ctypes.c_void_p),('TargetAlias',wintypes.LPWSTR),('UserName',wintypes.LPWSTR)]

def read_selected_vault_for_user_action():
    """Called only from the user's target-specific Connect callback worker."""
    api=ctypes.WinDLL('Advapi32.dll',use_last_error=True)
    api.CredReadW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype=wintypes.BOOL;api.CredFree.argtypes=[ctypes.c_void_p]
    pointer=ctypes.POINTER(Credential)();raw=None;key=None;ssid=None
    if not api.CredReadW(TARGET,1,0,ctypes.byref(pointer)):raise RuntimeError('Vault entry unavailable')
    try:
        entry=pointer.contents
        if entry.CredentialBlobSize<2 or entry.CredentialBlobSize>512 or entry.CredentialBlobSize%2:
            raise RuntimeError('Unsupported vault encoding')
        raw=bytearray(entry.CredentialBlobSize)
        ctypes.memmove((ctypes.c_ubyte*len(raw)).from_buffer(raw),entry.CredentialBlob,len(raw))
        ssid=bytearray(entry.UserName.encode('utf-8'));key=bytearray(raw.decode('utf-16-le').encode('utf-8'))
        # Validate lengths without creating VM code or writing a file.
        packet=encode_request(2,1,ssid,key);wipe(packet)
        return ssid,key
    except Exception:
        if ssid is not None:wipe(ssid)
        if key is not None:wipe(key)
        raise
    finally:
        if raw is not None:wipe(raw)
        # Clear only the returned local allocation, then release it. The
        # protected reusable Windows credential itself remains unchanged.
        if pointer and pointer.contents.CredentialBlob:
            ctypes.memset(pointer.contents.CredentialBlob,0,pointer.contents.CredentialBlobSize)
        api.CredFree(pointer)

def self_test():
    fixture_name=bytearray(b'Test');fixture_key=bytearray(b'unit-key')
    packet=encode_request(2,123,fixture_name,fixture_key)
    assert packet[:5]==bytes([251,205,0,25,0]) and packet[-1]==254 and len(packet)==30
    wipe(packet);assert not any(packet)
    for operation in (1,3):
        packet=encode_request(operation,123);assert len(packet)==16;wipe(packet)
    for sn,kn in ((0,8),(33,8),(4,7),(4,65)):
        try:encode_request(2,123,b'S'*sn,b'k'*kn)
        except ValueError:pass
        else:raise AssertionError('Unbounded setup request accepted')
    wipe(fixture_name);wipe(fixture_key)
    assert not any(fixture_name) and not any(fixture_key)
    print('PASS: setup envelope bounds and buffer clearing; no vault/USB/network access')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',action='store_true');parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--port',default='COM8')
    parser.add_argument('--receipt',type=Path,default=Path(__file__).resolve().parents[2]/'.private/electronics-wifi-vault/provisioning-status.json')
    args=parser.parse_args()
    if args.self_test:self_test();return
    if args.probe:
        client=SetupClient(args.port)
        try:print(json.dumps(client.probe()))
        finally:client.close()
        return
    import tkinter as tk
    from tkinter import ttk
    root=tk.Tk();root.title('Fruit Jam — connexion Wi-Fi');root.geometry('800x450')
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Connecter le Fruit Jam au Wi-Fi enregistré',font=('Segoe UI',15,'bold')).pack(anchor='w')
    ttk.Label(frame,wraplength=740,justify='left',text=
      'Cible : Fruit Jam USB COM8 — E46570978F1E5A34.\n'
      'Ton clic lit l’entrée Wi-Fi du coffre Windows et l’envoie à cette carte.\n'
      'Le mot de passe reste masqué et ne sera pas enregistré dans les programmes.\n'
      'La conservation sur la carte et le démarrage automatique du Wi-Fi ne sont pas encore activés.').pack(anchor='w',pady=18)
    status=tk.StringVar(value='Prêt. Le mot de passe enregistré n’a pas été lu par cet outil.')
    ttk.Label(frame,textvariable=status,wraplength=740,justify='left').pack(anchor='w',pady=18)
    events=queue.Queue();running=False
    def worker():
        client=None;ssid=None;key=None;before=None
        receipt={'result':'FAIL','started_utc':datetime.now(timezone.utc).isoformat(),
          'user_clicked_connect':True,'target_usb_serial':'E46570978F1E5A34','target_port':args.port,
          'credential_values_logged':False,'credential_payload_written':False,'accepted':False,
          'association_verified':False,'dhcp_verified':False,'programs_unchanged':False}
        try:
            events.put('Vérification de la carte cible et du protocole de configuration…')
            client=SetupClient(args.port);client.probe();before=client.vm.all_crcs()
            ssid,key=read_selected_vault_for_user_action()
            events.put('Envoi à la carte vérifiée ; association en cours…')
            answer=client.request(2,ssid,key)
            wipe(ssid);wipe(key);ssid=key=None
            receipt['credential_payload_written']=client.payload_written
            receipt['accepted']=answer['accepted']
            if not answer['accepted']:raise RuntimeError('Board rejected setup request')
            generation=answer['status']['generation'];deadline=time.monotonic()+65
            arithmetic_checks=0
            while time.monotonic()<deadline:
                current=client.request(3)['status']
                if current['generation']==generation and current['state'] in (3,4):break
                if before.get(0)==0x297d191b:
                    assert client.vm.run_reporter(0)==12;arithmetic_checks+=1
                events.put('Association et obtention d’une adresse IP…')
                time.sleep(.5)
            else:raise TimeoutError('Bounded board setup deadline exceeded')
            receipt['status']=current;receipt['arithmetic_during_association']=arithmetic_checks
            receipt['association_verified']=current['connection']==3
            receipt['dhcp_verified']=bool(current.get('network_ready'))
            assert current['state']==3 and current['error']==0 and receipt['dhcp_verified'],'Association or DHCP not verified'
            assert client.vm.all_crcs()==before,'Program CRC changed'
            receipt['programs_unchanged']=True
            if before.get(0)==0x297d191b:assert client.vm.run_reporter(0)==12
            client.close();client=None
            client=SetupClient(args.port)
            assert client.vm.all_crcs()==before
            if before.get(0)==0x297d191b:assert client.vm.run_reporter(0)==12
            receipt['usb_reconnect_verified']=True;receipt['result']='PASS'
            events.put('Connecté : '+current['ip']+' — USB et programmes vérifiés.')
        except Exception as exc:
            if client:receipt['credential_payload_written']=client.payload_written
            # Exception classes/codes only: never format a credential value.
            receipt['error_type']=type(exc).__name__
            events.put('Connexion non validée ('+type(exc).__name__+'). Le diagnostic ne contient aucun mot de passe.')
        finally:
            if ssid is not None:wipe(ssid)
            if key is not None:wipe(key)
            if client:
                try:
                    if before is not None:receipt['programs_unchanged']=client.vm.all_crcs()==before
                except Exception:pass
                client.close()
            receipt['finished_utc']=datetime.now(timezone.utc).isoformat()
            try:
                args.receipt.parent.mkdir(parents=True,exist_ok=True)
                attempt_stamp=datetime.fromisoformat(receipt['started_utc']).strftime('%Y%m%dT%H%M%S%fZ')
                attempt_path=args.receipt.with_name(args.receipt.stem+'-'+attempt_stamp+args.receipt.suffix)
                with attempt_path.open('x',encoding='utf-8',newline='\n') as attempt:
                    attempt.write(json.dumps(receipt,indent=2)+'\n')
                args.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
            except Exception:events.put('Le reçu local n’a pas pu être écrit ; garde cette fenêtre ouverte.')
            events.put(None)
    def connect():
        nonlocal running
        if running:return
        running=True;button.state(['disabled']);threading.Thread(target=worker,daemon=True).start()
    def drain():
        nonlocal running
        try:
            while True:
                event=events.get_nowait()
                if event is None:running=False;button.state(['!disabled'])
                else:status.set(event)
        except queue.Empty:pass
        root.after(100,drain)
    def close():
        if running:status.set('Connexion en cours. Attends le résultat avant de fermer.')
        else:root.destroy()
    button=ttk.Button(frame,text='Connecter ce Fruit Jam avec le Wi-Fi du coffre Windows',command=connect);button.pack(anchor='w',pady=16)
    ttk.Button(frame,text='Fermer',command=close).pack(anchor='e')
    root.protocol('WM_DELETE_WINDOW',close);root.after(100,drain);root.mainloop()

if __name__=='__main__':main()
