"""Bounded GET/POST to one configured origin using the official requests API."""
# SPDX-License-Identifier: MIT
import base64
import re
import time
from urllib.parse import urlsplit,urlunsplit
from ..api import ExtensionError,arguments,text


class Extension:
    def __init__(self,settings,context):
        if set(settings)-{'origin','allow_http','max_body_bytes','connect_timeout','read_timeout','total_timeout'}:raise ExtensionError('configuration','Unknown HTTP extension setting')
        self.origin=settings.get('origin','');url=urlsplit(self.origin)
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:raise ExtensionError('configuration','HTTP requires one configured origin without credentials or a path')
        if url.scheme=='http' and settings.get('allow_http') is not True:raise ExtensionError('configuration','Plain HTTP must be explicitly enabled for this configured origin')
        self.origin=urlunsplit((url.scheme,url.netloc,'','',''))
        self.maximum=settings.get('max_body_bytes',16384);self.connect=settings.get('connect_timeout',.5);self.read_timeout=settings.get('read_timeout',.5);self.total=settings.get('total_timeout',1.5)
        if type(self.maximum) is not int or not 1<=self.maximum<=16384 or any(type(v) not in (int,float) or not .05<=v<=3 for v in [self.connect,self.read_timeout,self.total]):raise ExtensionError('configuration','HTTP timeout or byte bounds are invalid')
        self.operations={'get':lambda args:self.request('GET',args),'post':lambda args:self.request('POST',args)}

    def request(self,method,args):
        arguments(args,{'path','headers','body'},{'path'})
        path=text(args['path'],2048,'HTTP path');url=urlsplit(path)
        if not path.startswith('/') or path.startswith('//') or url.scheme or url.netloc or url.fragment or '\\' in path or any(ord(c)<32 for c in path):raise ExtensionError('arguments','Use an HTTP path on the configured origin')
        headers=args.get('headers',[])
        if isinstance(headers,list):
            if len(headers)>24 or any(not isinstance(pair,list) or len(pair)!=2 or not isinstance(pair[0],str) or not isinstance(pair[1],str) for pair in headers):raise ExtensionError('arguments','HTTP headers must be header/value pairs')
            headers=dict(headers)
        if not isinstance(headers,dict) or len(headers)>24:raise ExtensionError('arguments','At most 24 HTTP headers are supported')
        denied={'host','content-length','transfer-encoding','connection','proxy-authorization','proxy-connection'}
        for name,value in headers.items():
            if type(name) is not str or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,64}",name) or name.lower() in denied:raise ExtensionError('arguments','Invalid or reserved HTTP header name')
            text(value,1024,'HTTP header')
            if '\r' in value or '\n' in value:raise ExtensionError('arguments','HTTP header values cannot contain line breaks')
        body=text(args.get('body',''),4096,'HTTP body')
        if method=='GET' and body:raise ExtensionError('arguments','GET does not send a request body')
        try:import requests
        except ImportError:raise ExtensionError('dependency_missing','Install the official requests package in the configured Python environment') from None
        started=time.monotonic();received=bytearray();truncated=False
        try:
            with requests.Session() as session:
                session.trust_env=False # no implicit proxy, netrc or environment credentials
                with session.request(method,self.origin+path,headers=headers,data=body.encode() if method=='POST' else None,
                    timeout=(self.connect,self.read_timeout),stream=True,allow_redirects=False,verify=True) as response:
                    for chunk in response.iter_content(1024):
                        if time.monotonic()-started>self.total:raise ExtensionError('timeout','HTTP response exceeded its total deadline','unknown' if method=='POST' else 'rejected')
                        available=self.maximum-len(received)
                        received.extend(chunk[:available])
                        if len(chunk)>available:truncated=True;break
                    try:
                        decoded=received.decode('utf-8')
                        if '\0' in decoded:raise UnicodeError('binary')
                        encoding='utf-8'
                    except UnicodeError:decoded=base64.b64encode(received).decode('ascii');encoding='base64'
                    visible={str(k).lower():str(v)[:1024] for k,v in list(response.headers.items())[:24]}
                    return {'status':response.status_code,'headers':visible,'body':decoded,'body_encoding':encoding,
                        'truncated':truncated,'headers_limited':len(response.headers)>24 or any(len(str(v))>1024 for v in response.headers.values()),
                        'redirect_followed':False}
        except requests.RequestException:raise ExtensionError('http_error','HTTP request failed; check the configured server, connection and TLS certificate','unknown' if method=='POST' else 'rejected') from None
