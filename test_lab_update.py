import hashlib,json,tempfile,unittest
from pathlib import Path
from apply_lab_update import apply

class UpdateTests(unittest.TestCase):
    def bundle(self,root):
        package=root/'package';target=root/'live';(package/'files').mkdir(parents=True);target.mkdir()
        records=[]
        for name in ('native_carla.py','navigation.js'):
            (target/name).write_bytes(b'baseline');(package/'files'/name).write_bytes(b'updated')
            records.append(dict(path=name,previous_sha256=hashlib.sha256(b'baseline').hexdigest(),sha256=hashlib.sha256(b'updated').hexdigest()))
        (package/'manifest.json').write_text(json.dumps(dict(version='test',files=records)));return package,target
    def test_baseline_update_keeps_backup_and_local_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            p,t=self.bundle(Path(folder));(t/'lab.local.json').write_bytes(b'lab calibration')
            result=apply(p,t);self.assertTrue(result['applied']);self.assertEqual((t/'native_carla.py').read_bytes(),b'updated')
            self.assertEqual((Path(result['backup'])/'native_carla.py').read_bytes(),b'baseline');self.assertEqual((t/'lab.local.json').read_bytes(),b'lab calibration')
            self.assertEqual(apply(p,t)['updated'],0)
    def test_websocket_lab_edits_abort_whole_update(self):
        with tempfile.TemporaryDirectory() as folder:
            p,t=self.bundle(Path(folder));(t/'native_carla.py').write_bytes(b'lab websocket integration')
            result=apply(p,t);self.assertFalse(result['applied']);self.assertEqual((t/'native_carla.py').read_bytes(),b'lab websocket integration');self.assertEqual((t/'navigation.js').read_bytes(),b'baseline')
    def test_corrupt_payload_is_not_installed(self):
        with tempfile.TemporaryDirectory() as folder:
            p,t=self.bundle(Path(folder));(p/'files/native_carla.py').write_bytes(b'corrupted')
            with self.assertRaises(ValueError):apply(p,t)
            self.assertEqual((t/'native_carla.py').read_bytes(),b'baseline')
    def test_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p,t=self.bundle(Path(folder));m=json.loads((p/'manifest.json').read_text());m['files'][0]['path']='../private.txt';(p/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):apply(p,t)

if __name__=='__main__':unittest.main()
