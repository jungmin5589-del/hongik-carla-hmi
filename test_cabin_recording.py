import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cabin_recording as cabin


class Request:
    def __init__(self,range_header=None):self.headers={} if range_header is None else {'Range':range_header};self.wfile=io.BytesIO();self.reply={}
    def send_response(self,c):self.code=c
    def send_header(self,k,v):self.reply[k]=v
    def end_headers(self):pass
    def send_error(self,c,*_):self.code=c


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.content=bytes(range(256))*8
        (self.root/cabin.FILENAME).write_bytes(self.content)
        self.record=dict(filename=cabin.FILENAME,license='CC0-1.0',title='Field recording',author='Author',source_url='https://example.com/source',sha256=hashlib.sha256(self.content).hexdigest())
        (self.root/'manifest.json').write_text(json.dumps(self.record))
        self.cache=patch.object(cabin,'CACHE',self.root);self.cache.start();cabin.verified.cache_clear()
    def tearDown(self):cabin.verified.cache_clear();self.cache.stop();self.temp.cleanup()
    def test_source_and_ranges(self):
        self.assertTrue(cabin.catalog()['recorded_elsewhere'])
        for header,expected,code in [(None,self.content,200),('bytes=0-127',self.content[:128],206),('bytes=-17',self.content[-17:],206),('bytes=2000-',self.content[2000:],206)]:
            req=Request(header);cabin.stream(req);self.assertEqual(req.code,code);self.assertEqual(req.wfile.getvalue(),expected)
        req=Request('bytes=0-127');cabin.stream(req,head=True);self.assertEqual(req.code,206);self.assertEqual(req.reply['Content-Length'],'128');self.assertEqual(req.wfile.getvalue(),b'')
    def test_bad_ranges_and_tampering(self):
        for header in ['bytes=0-1,3-4','bytes=3000-','bytes=-0','bytes=7-1']:
            req=Request(header);cabin.stream(req);self.assertEqual(req.code,416)
        cabin.verified.cache_clear();(self.root/cabin.FILENAME).write_bytes(b'x'*2048)
        self.assertFalse(cabin.catalog()['available']);req=Request();cabin.stream(req);self.assertEqual(req.code,503)
    def test_missing_asset_has_no_synthetic_fallback(self):
        (self.root/cabin.FILENAME).unlink();self.assertFalse(cabin.catalog()['available'])


if __name__=='__main__':unittest.main()
