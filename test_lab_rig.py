import io,json,unittest,zipfile,tempfile
from pathlib import Path
from setup_lab import prepare_engine
from lab_capture import FrameBundle,inspection_jpeg
from lab_settings import DEFAULTS,view_yaws,sun_altitude
from lab_viewer import surround_rect

class RigTests(unittest.TestCase):
    def test_original_carpool_daylight_and_night_are_separate(self):
        self.assertEqual(sun_altitude('carpool'),12);self.assertEqual(sun_altitude('night'),-8)
    def test_source_calibration_and_adjacent_edges(self):
        cfg=DEFAULTS;y=view_yaws(cfg);self.assertEqual(list(y.values()),[-66,6,78])
        self.assertEqual(y['left']+cfg['fov']/2,y['center']-cfg['fov']/2)
        self.assertEqual(y['center']+cfg['fov']/2,y['right']-cfg['fov']/2)
        self.assertFalse(cfg['motion_enabled'])
    def test_no_normal_monitor_is_mistaken_for_surround(self):
        self.assertIsNone(surround_rect([[0,0,1920,1080],[1920,0,2560,1440]]))
        self.assertEqual(surround_rect([[0,0,1920,1080],[1920,-1080,5760,1080]]),[1920,-1080,5760,1080])
    def test_three_views_must_share_a_frame(self):
        f=FrameBundle();f.publish('left',10,b'L');f.publish('center',10,b'C');f.publish('right',11,b'R')
        self.assertIsNone(f.after(-1,0)[1]);f.publish('right',10,b'R')
        frame,data=f.after(-1,0);self.assertEqual(frame,10)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(json.loads(z.read('frame.json'))['frame'],10);self.assertEqual(z.read('left.jpg'),b'L')
        self.assertIsNone(f.after(10,0)[1]);f.close();self.assertIsNone(f.after(-1,0)[1])
    def test_missing_views_do_not_accumulate_frames(self):
        f=FrameBundle()
        for i in range(100):f.publish('left',i,b'L')
        self.assertLessEqual(len(f.pending),6)
        with self.assertRaises(ValueError):f.publish('../private',101,b'X')

    def test_existing_lab_engine_cannot_be_overwritten_by_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'installed-lab-engine';old.mkdir();(old/'CarlaUE4.exe').write_bytes(b'keep old engine')
            with zipfile.ZipFile(root/'CARLA_0.9.16.zip','w') as z:z.writestr('CarlaUE4.exe',b'new engine')
            prepare_engine(old,root);self.assertEqual((old/'CarlaUE4.exe').read_bytes(),b'keep old engine')
            existing=root/'CARLA_0.9.16';existing.mkdir();(existing/'CarlaUE4.exe').write_bytes(b'keep this too')
            with self.assertRaisesRegex(RuntimeError,'left untouched'):prepare_engine(existing,root)
            self.assertEqual((existing/'CarlaUE4.exe').read_bytes(),b'keep this too')
    def test_inspection_enlarges_center_without_mutating_panorama_bytes(self):
        from PIL import Image,ImageDraw
        im=Image.new('RGB',(800,450),'red');ImageDraw.Draw(im).rectangle((80,0,720,450),fill='blue')
        out=io.BytesIO();im.save(out,format='JPEG');original=out.getvalue()
        enlarged=Image.open(io.BytesIO(inspection_jpeg(original,72)))
        self.assertEqual(enlarged.size,(800,450));self.assertGreater(enlarged.getpixel((5,225))[2],200)
        self.assertGreater(Image.open(io.BytesIO(original)).getpixel((5,225))[0],200)

if __name__=='__main__':unittest.main()
