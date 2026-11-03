import hashlib,json,tempfile,wave,unittest
from pathlib import Path
from unittest.mock import patch
import mechanical_recording as sound

class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.patch=patch.object(sound,'CACHE',self.root);self.patch.start()
        p=self.root/'soft-metal-scrape.wav'
        with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*48000)
        (self.root/'manifest.json').write_text(json.dumps(dict(filename=p.name,license='CC-BY-4.0',sha256=hashlib.sha256(p.read_bytes()).hexdigest())))
        sound.audio.cache_clear()
    def tearDown(self):sound.audio.cache_clear();self.patch.stop();self.temp.cleanup()
    def test_attribution_and_verified_audio(self):
        self.assertTrue(sound.metadata()['available']);self.assertEqual(sound.metadata()['author'],'Doctor_Jekyll');self.assertGreater(len(sound.audio()),90000)
    def test_tampered_or_missing_is_unavailable(self):
        p=self.root/'soft-metal-scrape.wav';p.write_bytes(b'changed');self.assertFalse(sound.metadata()['available'])
        p.unlink();self.assertFalse(sound.metadata()['available'])
    def test_manifest_cannot_select_another_file(self):
        p=self.root/'manifest.json';r=json.loads(p.read_text());r['filename']='../../secret.wav';p.write_text(json.dumps(r))
        self.assertFalse(sound.metadata()['available'])

if __name__=='__main__':unittest.main()
