import io,unittest
from types import SimpleNamespace
import numpy as np
from PIL import Image
from high_beam import HighBeamSignal,HighBeamEffect


class SignalTests(unittest.TestCase):
    def test_requires_rendered_on_off_on_off_and_pause_freezes(self):
        s=HighBeamSignal();s.begin()
        for _ in range(20):s.advance(.1,True)
        self.assertEqual(s.stage,0) # A successful command alone is not visible proof.
        s.acknowledge(s.count,0)
        for _ in range(20):s.advance(.1,False)
        self.assertEqual(s.stage,0)
        s.advance(.1,True);self.assertEqual(s.stage,1);self.assertFalse(s.public()['on'])
        for stage in (1,2,3):
            s.acknowledge(s.count,stage)
            for _ in range(12):s.advance(.1,True)
        self.assertTrue(s.finished);self.assertFalse(s.public()['on'])

    def test_stale_frame_cannot_acknowledge_another_flash(self):
        s=HighBeamSignal();s.begin();s.acknowledge(0,0)
        self.assertFalse(s.ack)
        s.acknowledge(1,0);s.advance(.2,True);s.begin();s.acknowledge(1,0)
        self.assertFalse(s.ack);self.assertEqual(s.count,2)


class EffectTests(unittest.TestCase):
    def setUp(self):
        f=SimpleNamespace(principal_point_x=320.,principal_point_y=180.,pixeldist_to_angle_poly=[0.,.002])
        intr=SimpleNamespace(ftheta_param=f,resolution_w=640,resolution_h=360,WhichOneof=lambda name:'ftheta_param')
        self.effect=HighBeamEffect();self.effect.configure(intr)
        self.camera=np.eye(4);self.camera[:3,:3]=[[0,0,1],[-1,0,0],[0,-1,0]];self.camera[2,3]=1.4
        self.ego=np.eye(4);b=io.BytesIO();Image.new('RGB',(640,360),(80,80,80)).save(b,format='JPEG');self.jpeg=b.getvalue()

    def test_off_is_unchanged_on_lights_ground_not_sky(self):
        args=(self.jpeg,self.camera,self.ego,np.zeros(3),np.array([0,0,1]),[])
        off,_=self.effect.apply(*args,dict(on=False));self.assertEqual(off,self.jpeg)
        lit,record=self.effect.apply(*args,dict(on=True))
        a=np.asarray(Image.open(io.BytesIO(self.jpeg)),dtype=float);b=np.asarray(Image.open(io.BytesIO(lit)),dtype=float)
        self.assertLess(np.abs((b-a)[:100]).max(),3)
        self.assertGreater((b-a)[220:].mean(),5)
        self.assertGreater((b-a)[220:].max(),20)
        self.assertGreater(record['lit_fraction'],.1)

    def test_near_box_blocks_ground_ray(self):
        pose=np.eye(4);pose[0,3]=10;pose[2,3]=1.
        result=self.effect.box_range(np.array([0,0,1.]),np.array([[1.,0,0],[0,1.,0]]),pose,[4,2,2])
        self.assertAlmostEqual(result[0],8.);self.assertTrue(np.isinf(result[1]))

if __name__=='__main__':unittest.main()
