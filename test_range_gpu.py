import unittest
import torch
from range_transport import encode_range_hint,decode_range_hint,compose_native_fog

class RangeTensorTests(unittest.TestCase):
    def test_surface_range_is_encoded_and_empty_sky_has_far_sentinel(self):
        distance=torch.full((720,1280),16.);opacity=torch.ones_like(distance);opacity[:360]=0.
        data=encode_range_hint(distance,opacity,123)
        result=decode_range_hint(data,123)
        self.assertTrue((result[:67]==500.).all());self.assertTrue((result[68:]==16.).all())
        self.assertLess(len(data),128*1024)
    def test_gpu_math_matches_beer_lambert_and_handles_empty_sky(self):
        import numpy as np
        color=torch.full((24,32,3),.25);distance=torch.full((24,32),16.);opacity=torch.ones_like(distance);opacity[:4]=0.
        beta=.08;t=180.
        output=compose_native_fog(color,distance,opacity,beta,t).numpy()
        y,x=np.mgrid[:24,:32].astype(np.float32);x/=32;y/=24
        eddies=.025*np.sin(x*13+y*7+t*.07)+.015*np.sin(x*7-y*9-t*.05)
        ranges=np.full((24,32),16.,dtype=np.float32);ranges[:4]=500.
        transmission=np.exp(-ranges*beta*(1+eddies))[...,None]
        reference=(.25**2.2*transmission+np.array([.79,.82,.84],dtype=np.float32)**2.2*(1-transmission))**(1/2.2)
        np.testing.assert_allclose(output,reference,atol=1e-6)
        self.assertIsNone(compose_native_fog(color,None,None,beta,t))
    def test_translucent_sky_is_not_interpreted_as_a_near_surface(self):
        color=torch.full((24,32,3),.25);distance=torch.full((24,32),.2)
        alpha=torch.full_like(distance,.1)
        fog=compose_native_fog(color,distance,alpha,.08,180.)
        air=torch.tensor([.79,.82,.84])
        self.assertTrue(torch.allclose(fog,air.expand_as(fog),atol=1e-5))
        ranges=decode_range_hint(encode_range_hint(distance,alpha,123),123)
        self.assertTrue((ranges==500.).all())
    def test_missing_near_road_depth_uses_the_same_frame_ground_plane(self):
        h,w=64,96
        y,x=torch.meshgrid(torch.linspace(-.1,-.7,h),torch.linspace(-.7,.7,w),indexing='ij')
        direction=torch.stack((x,torch.ones_like(x),y),dim=-1)
        direction=direction/torch.linalg.vector_norm(direction,dim=-1,keepdim=True)
        distance=-1.5/direction[...,2]
        color=torch.full((h,w,3),.25);alpha=torch.ones_like(distance)
        expected=compose_native_fog(color,distance,alpha,.08,180.)
        alpha[-16:,:12]=0.;raw=distance*alpha
        rays=torch.cat((torch.zeros_like(direction),direction),dim=-1)
        actual=compose_native_fog(color,raw,alpha,.08,180.,rays)
        self.assertTrue(torch.allclose(actual[-16:,:12],expected[-16:,:12],atol=2e-4))
    def test_no_distance_returns_no_side_channel(self):self.assertIsNone(encode_range_hint(None,None,123))
    def test_missing_ground_past_thirty_metres_does_not_turn_into_white_band(self):
        h,w=64,96
        y,x=torch.meshgrid(torch.linspace(-.015,-.7,h),torch.linspace(-.7,.7,w),indexing='ij')
        direction=torch.stack((x,torch.ones_like(x),y),dim=-1)
        direction=direction/torch.linalg.vector_norm(direction,dim=-1,keepdim=True)
        distance=-1.5/direction[...,2];color=torch.full((h,w,3),.25);alpha=torch.ones_like(distance)
        expected=compose_native_fog(color,distance,alpha,.012,60.)
        alpha[:5,:20]=0.
        rays=torch.cat((torch.zeros_like(direction),direction),dim=-1)
        actual=compose_native_fog(color,distance*alpha,alpha,.012,60.,rays)
        self.assertTrue(torch.allclose(actual[:5,:20],expected[:5,:20],atol=1e-3))
    def test_opaque_but_wrong_far_shoulder_is_capped_without_erasing_foreground(self):
        h,w=64,96
        y,x=torch.meshgrid(torch.linspace(-.015,-.7,h),torch.linspace(-.7,.7,w),indexing='ij')
        direction=torch.stack((x,torch.ones_like(x),y),dim=-1);direction/=torch.linalg.vector_norm(direction,dim=-1,keepdim=True)
        distance=-1.5/direction[...,2];color=torch.full((h,w,3),.25);alpha=torch.ones_like(distance)
        rays=torch.cat((torch.zeros_like(direction),direction),dim=-1)
        expected=compose_native_fog(color,distance,alpha,.025,65.)
        wrong=distance.clone();wrong[15:30,:20]=300.
        # A nearer raised foreground must retain its original surface range.
        wrong[15:20,45:50]=2.
        actual=compose_native_fog(color,wrong,alpha,.025,65.,rays)
        self.assertTrue(torch.allclose(actual[15:30,:20],expected[15:30,:20],atol=1e-3))
        foreground=compose_native_fog(color,wrong,alpha,.025,65.)
        self.assertTrue(torch.allclose(actual[15:20,45:50],foreground[15:20,45:50],atol=1e-6))

if __name__=='__main__':unittest.main()
