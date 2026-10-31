"""Actual HTTP media range/HEAD/path boundary and passenger template checks."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from native_carla import handler,native_navigation_html,nav_js
import passenger_music

class MusicHTTPTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.patch=patch.object(passenger_music,'MUSIC',Path(cls.temp.name));cls.patch.start()
  cls.bytes=bytes(range(256));(Path(cls.temp.name)/'yerin.flac').write_bytes(cls.bytes)
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler(SimpleNamespace()));cls.server.daemon_threads=True
  cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.worker.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.worker.join();cls.patch.stop();cls.temp.cleanup()
 def request(self,path,**kwargs):return urllib.request.urlopen(urllib.request.Request(self.url+path,**kwargs))
 def test_library_has_original_metadata_without_local_paths(self):
  with self.request('/api/library') as r:data=json.load(r)
  self.assertEqual(len(data['tracks']),5);self.assertTrue(data['tracks'][0]['available']);self.assertFalse(data['tracks'][1]['available'])
  self.assertNotIn(self.temp.name,json.dumps(data))
 def test_audio_range_is_seekable(self):
  with self.request('/media/yerin',headers={'Range':'bytes=32-63'}) as r:
   self.assertEqual(r.status,206);self.assertEqual(r.read(),self.bytes[32:64]);self.assertEqual(r.headers['Content-Range'],'bytes 32-63/256')
 def test_head_and_invalid_range(self):
  with self.request('/media/yerin',method='HEAD',headers={'Range':'bytes=-8'}) as r:self.assertEqual(r.status,206);self.assertEqual(r.headers['Content-Length'],'8');self.assertEqual(r.read(),b'')
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/media/yerin',headers={'Range':'bytes=300-'})
  self.assertEqual(e.exception.code,416)
 def test_track_identifier_cannot_read_other_files(self):
  for path in ['/media/../native-owned.json','/media/yerin/extra']:
   with self.assertRaises(urllib.error.HTTPError) as e:self.request(path)
   self.assertEqual(e.exception.code,404)
 def test_navigation_has_music_and_no_experience_wording(self):
  html=native_navigation_html().decode();js=nav_js().decode()
  self.assertIn('music-dock',html);self.assertIn('/underbody-sound.js',html)
  self.assertNotIn('체험',html);self.assertNotIn('체험',js)
  self.assertIn("$('settings-sheet').append(bar)",js)

if __name__=='__main__':unittest.main()
