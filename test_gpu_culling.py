"""CPU tensor checks, run with the existing official container's torch runtime."""
import math
from types import SimpleNamespace as NS
import unittest
import torch
from lean_runtime import camera_visible_parameters


class CameraCullingTests(unittest.TestCase):
    def data(self,q=(0,0,0,1)):
        return NS(sensor_model_parameters=[NS(max_angle=math.pi/3)],
            poses_tquat_startend=torch.tensor([[[0.,0.,0.,*q],[0.,0.,0.,*q]]]))
    def parameters(self,points,scales=None):
        n=len(points)
        return dict(positions=torch.tensor(points,dtype=torch.float32),
            scales=torch.full((n,3),.01) if scales is None else torch.tensor(scales),
            features=torch.arange(n*3).reshape(n,3),metadata='unchanged')
    def test_front_is_kept_rear_and_far_side_are_excluded_with_all_attributes_aligned(self):
        original=self.parameters([[0,0,10],[0,0,-10],[20,0,1]])
        result=camera_visible_parameters(self.data(),original)
        self.assertEqual(result['positions'].tolist(),[[0.,0.,10.]])
        self.assertEqual(result['features'].tolist(),[[0,1,2]])
        self.assertEqual(result['metadata'],'unchanged')
        self.assertEqual(len(original['positions']),3)
    def test_camera_rotation_and_large_silhouette_bounds(self):
        value=self.parameters([[10,0,0],[0,0,10]])
        result=camera_visible_parameters(self.data((0,math.sqrt(.5),0,math.sqrt(.5))),value)
        self.assertEqual(result['positions'].tolist(),[[10.,0.,0.]])
        value=self.parameters([[0,0,10],[0,0,-1]],[[.01,.01,.01],[2.,2.,2.]])
        self.assertEqual(len(camera_visible_parameters(self.data(),value)['positions']),2)
    def test_unknown_camera_log_scale_or_suspicious_empty_result_falls_back_safely(self):
        value=self.parameters([[0,0,-10],[0,0,-20]])
        self.assertIs(camera_visible_parameters(self.data(),value),value)
        data=self.data();data.sensor_model_parameters=[NS()]
        self.assertIs(camera_visible_parameters(data,value),value)
        value=self.parameters([[0,0,10],[0,0,-10]],[[-1.,-1.,-1.],[-1.,-1.,-1.]])
        self.assertIs(camera_visible_parameters(self.data(),value),value)


if __name__=='__main__':unittest.main()
