#!/usr/bin/env python3
"""One local masked station entry; Windows-user DPAPI handoff, status only.

No Wi-Fi association, board access, Windows credential lookup or plaintext file.
Delete the encrypted handoff after verified P4 provisioning.
"""
# SPDX-License-Identifier: MIT
import argparse,ctypes,datetime,json,os,re
from ctypes import wintypes
from pathlib import Path

class Blob(ctypes.Structure):
 _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def protect(raw):
 if os.name!='nt':raise RuntimeError('Windows local user required')
 source=ctypes.create_string_buffer(raw);value=Blob(len(raw),ctypes.cast(source,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
 crypto=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 crypto.CryptProtectData.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
 crypto.CryptProtectData.restype=wintypes.BOOL;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
 try:
  if not crypto.CryptProtectData(ctypes.byref(value),'MicroBlocks P4 station handoff',None,None,None,1,ctypes.byref(out)):raise RuntimeError('Windows DPAPI protection failed')
  return ctypes.string_at(out.data,out.size)
 finally:
  ctypes.memset(source,0,len(source))
  if out.data:kernel.LocalFree(out.data)

def main(a):
 import tkinter as tk
 from tkinter import ttk
 root=Path(__file__).resolve().parents[1];private=root/'secrets';receipt=root/'build-artifacts/p4-station-entry/status.json';handoff=private/'p4-station-handoff.dpapi';lock=private/'p4-station-entry.lock'
 private.mkdir(exist_ok=True);receipt.parent.mkdir(parents=True,exist_ok=True)
 def status(state,**extra):
  report=dict(status=state,updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),destination='ESP32-P4 COM5 station Wi-Fi',ssid_present=False,password_present=False,persist_on_board_authorized=True,plaintext_written=False,board_configuration_applied=False,**extra)
  temp=receipt.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2)+'\n',newline='\n');os.replace(temp,receipt)
 if handoff.exists():
  print('Existing encrypted station handoff retained; no second prompt or receipt replacement.');return
 try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 except FileExistsError:raise RuntimeError('Existing station dialog lock; do not create a second prompt')
 os.write(fd,str(os.getpid()).encode());os.close(fd)
 window=None
 try:
  # Verify the supported OS encryption API before requesting any credentials.
  if not protect(b'P4 station prompt self-test'):raise RuntimeError('Secure storage unavailable')
  window=tk.Tk();window.title('Connect ESP32-P4 to your Wi-Fi');window.resizable(False,False);window.attributes('-topmost',True)
  frame=ttk.Frame(window,padding=20);frame.grid();ttk.Label(frame,text='ESP32-P4 on COM5 — saved Wi-Fi reconnection',font=('Segoe UI',12,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,12))
  ttk.Label(frame,text='Enter your 2.4 GHz WPA2-Personal network.\nThe board will reconnect after restart, as you approved.').grid(row=1,column=0,columnspan=2,sticky='w',pady=(0,12))
  ttk.Label(frame,text='Wi-Fi network name (SSID)').grid(row=2,column=0,sticky='w');ssid=ttk.Entry(frame,width=43);ssid.grid(row=2,column=1,pady=6)
  ttk.Label(frame,text='Wi-Fi password').grid(row=3,column=0,sticky='w');password=ttk.Entry(frame,width=43,show='\u2022');password.grid(row=3,column=1,pady=6)
  notice=ttk.Label(frame,text='',foreground='#a02020',wraplength=490);notice.grid(row=4,column=0,columnspan=2,sticky='w',pady=6)
  ttk.Label(frame,text='Temporary handoff is encrypted for your Windows login.\nIt will be removed after board verification.\nNo Windows Wi-Fi settings are changed.',wraplength=490).grid(row=5,column=0,columnspan=2,sticky='w',pady=(8,12))
  submitted=False
  def cancel():
   password.delete(0,tk.END);status('cancelled');window.destroy()
  def save():
   nonlocal submitted
   name=ssid.get();key=password.get();sn=name.encode('utf8');kn=key.encode('utf8')
   if not 1<=len(sn)<=32 or '\0' in name:notice.config(text='Enter a network name of 1..32 UTF-8 bytes.');return
   if not (8<=len(kn)<=63 or len(kn)==64 and re.fullmatch(r'[0-9a-fA-F]{64}',key)) or '\0' in key:notice.config(text='Enter an 8..63-byte password, or a 64-digit hexadecimal key.');return
   try:
    data=json.dumps(dict(schema=1,ssid=name,password=key,security='WPA2-PSK',persist=True,destination='COM5 ESP32-P4'),ensure_ascii=False,separators=(',',':')).encode('utf8')
    protected=protect(data)
    with handoff.open('xb') as stream:stream.write(protected)
    password.delete(0,tk.END);ssid.delete(0,tk.END);name=key=data=sn=kn=None
    # Receipt deliberately omits SSID, password and any credential hash.
    report=dict(status='received',updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),destination='ESP32-P4 COM5 station Wi-Fi',ssid_present=True,password_present=True,persist_on_board_authorized=True,encrypted_handoff=True,plaintext_written=False,board_configuration_applied=False,retention='remove after verified board provisioning')
    receipt.write_text(json.dumps(report,indent=2)+'\n',newline='\n');submitted=True;window.destroy()
   except Exception:notice.config(text='Secure handoff could not be saved. No board configuration was attempted.')
  buttons=ttk.Frame(frame);buttons.grid(row=6,column=0,columnspan=2,sticky='e');ttk.Button(buttons,text='Cancel',command=cancel).grid(row=0,column=0,padx=6);ttk.Button(buttons,text='Save for the ESP32-P4',command=save).grid(row=0,column=1)
  window.protocol('WM_DELETE_WINDOW',cancel);window.bind('<Return>',lambda event:save());ssid.focus_set();window.update_idletasks();x=(window.winfo_screenwidth()-window.winfo_width())//2;y=(window.winfo_screenheight()-window.winfo_height())//2;window.geometry(f'+{x}+{y}')
  window.after(150,lambda:status('prompt_ready'));window.mainloop()
 finally:
  if lock.exists():lock.unlink()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approved-persistence',action='store_true');a=p.parse_args()
 if not a.approved_persistence:p.error('Explicit station credential storage authorization required')
 main(a)
