"""Installer checks use temporary fixtures, never the running experiment."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from apply_team_update import apply,approved

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.target=root/'app';self.package=root/'release'
        (self.target/'live').mkdir(parents=True);(self.target/'python').mkdir()
        (self.target/'live/native_carla.py').write_text('original')
        (self.target/'python/python.exe').write_bytes(b'fixture')
        (self.target/'live/lab.local.json').write_text('private settings')
        (self.target/'mobile-data').mkdir();(self.target/'mobile-data/private.pem').write_text('private fixture')
        payload=self.package/'files/live';payload.mkdir(parents=True)
        (payload/'native_carla.py').write_text('updated')
        self.manifest=dict(source_commit='fixture',files=[dict(path='live/native_carla.py',sha256=hashlib.sha256(b'updated').hexdigest())])
        self.save()
    def save(self):
        (self.package/'manifest.json').write_text(json.dumps(self.manifest))
    def test_check_does_not_write_and_apply_preserves_originals(self):
        self.assertEqual(apply(self.target,True,self.package)['changed'],1)
        self.assertEqual((self.target/'live/native_carla.py').read_text(),'original')
        with patch('apply_team_update.socket.socket') as sock:
            sock.return_value.__enter__.return_value.connect_ex.return_value=1
            result=apply(self.target,package=self.package)
        self.assertEqual((Path(result['backup'])/'live/native_carla.py').read_text(),'original')
        self.assertEqual((self.target/'live/native_carla.py').read_text(),'updated')
        self.assertEqual((self.target/'live/lab.local.json').read_text(),'private settings')
        self.assertEqual((self.target/'mobile-data/private.pem').read_text(),'private fixture')
        self.assertEqual(apply(self.target,True,self.package)['changed'],0)
    def test_checksum_failure_precedes_all_writes(self):
        (self.package/'files/live/native_carla.py').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'checksum'):apply(self.target,package=self.package)
        self.assertEqual((self.target/'live/native_carla.py').read_text(),'original')
        self.assertFalse((self.target/'update-backups').exists())
    def test_private_and_escape_paths_are_rejected(self):
        for name in ('../outside.py','live/../native_carla.py','live/lab.local.json',
                     'mobile-data/private.pem','cache/music/song.mp3','live/research.sqlite3',
                     'E:/outside.py','live\\native_carla.py','cache/research-voice/key.pem'):
            self.assertFalse(approved(name),name)
            self.manifest['files'][0]['path']=name;self.save()
            with self.assertRaises(ValueError):apply(self.target,True,self.package)
    def test_running_experiment_blocks_writes(self):
        with patch('apply_team_update.socket.socket') as sock:
            sock.return_value.__enter__.return_value.connect_ex.return_value=0
            with self.assertRaisesRegex(RuntimeError,'Close the driving app'):apply(self.target,package=self.package)
        self.assertEqual((self.target/'live/native_carla.py').read_text(),'original')
    def test_duplicate_payload_is_rejected(self):
        self.manifest['files']*=2;self.save()
        with self.assertRaisesRegex(ValueError,'duplicate'):apply(self.target,True,self.package)

if __name__=='__main__':unittest.main()
