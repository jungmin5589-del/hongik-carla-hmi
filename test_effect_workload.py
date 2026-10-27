import unittest
import numpy as np
from fog_effect import composite_fog_rgb

class FogCompositeTests(unittest.TestCase):
    def test_all_8bit_levels_and_transmission_extremes_preserve_the_previous_optics(self):
        rgb=np.repeat(np.arange(256,dtype=np.uint8)[None,:,None],3,axis=2)
        rgb=np.repeat(rgb,257,axis=0)
        alpha=np.linspace(0,1,257,dtype=np.float32)[:,None,None]
        linear=(rgb.astype(np.float32)/255.)**2.2
        air=np.array([.79,.82,.84],dtype=np.float32)**2.2
        reference=np.uint8(np.rint(np.clip(linear*alpha+air*(1-alpha),0,1)**(1/2.2)*255))
        output=composite_fog_rgb(rgb,alpha)
        self.assertLessEqual(np.abs(output.astype(int)-reference.astype(int)).max(),1)
        self.assertLessEqual(np.abs(output[-1].astype(int)-rgb[-1].astype(int)).max(),1)
        self.assertTrue(np.all(output[0]==output[0,0]))

if __name__=='__main__':unittest.main()
