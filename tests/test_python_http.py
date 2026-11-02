"""Only a local fixture is contacted; no external HTTP endpoint or dependency install."""
# SPDX-License-Identifier: MIT
import importlib.util
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from linux.extensions.api import Context,ExtensionError
from linux.extensions.plugins.http import Extension


class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/slow':time.sleep(.3)
        self.send_response(302 if self.path=='/redirect' else 200)
        self.send_header('Location','http://external.invalid/must-not-follow')
        self.send_header('X-Observed',self.headers.get('X-Example','none'));self.end_headers()
        try:self.wfile.write(b'\0\xff' if self.path=='/binary' else b'x'*100 if self.path=='/large' else b'local fixture')
        except BrokenPipeError:pass
    def do_POST(self):
        data=self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(201);self.end_headers();self.wfile.write(data)


@unittest.skipUnless(importlib.util.find_spec('requests'),'official requests dependency is not installed in this interpreter')
class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def extension(self,**settings):return Extension({'origin':f'http://127.0.0.1:{self.server.server_port}','allow_http':True,**settings},Context(Path('.'),'linux-test'))
    def test_real_requests_get_post_headers_redirect_and_binary(self):
        extension=self.extension()
        result=extension.request('GET',{'path':'/','headers':[['X-Example','header42']]})
        self.assertEqual((result['status'],result['body'],result['headers']['x-observed']),(200,'local fixture','header42'))
        self.assertEqual(extension.request('POST',{'path':'/','body':'quote\'é','headers':[]})['body'],"quote'é")
        self.assertEqual(extension.request('GET',{'path':'/redirect'})['status'],302)
        result=extension.request('GET',{'path':'/binary'});self.assertEqual((result['body'],result['body_encoding']),('AP8=','base64'))
    def test_bounds_timeouts_scope_and_headers(self):
        extension=self.extension(max_body_bytes=8,read_timeout=.1)
        result=extension.request('GET',{'path':'/large'});self.assertEqual(result['body'],'xxxxxxxx');self.assertTrue(result['truncated'])
        started=time.monotonic()
        with self.assertRaises(ExtensionError):extension.request('GET',{'path':'/slow'})
        self.assertLess(time.monotonic()-started,.6)
        for args in [{'path':'//external.invalid/'},{'path':'https://external.invalid/'},{'path':'/','headers':[['Host','other']]},{'path':'/','headers':[['x','a\r\nb']]},{'path':'/','headers':[[[],2]]}]:
            with self.assertRaises(ExtensionError):extension.request('GET',args)


if __name__=='__main__':unittest.main()
