"""Regression checks for movement/visual-orientation separation."""
import unittest
from types import SimpleNamespace
import carla
import numpy as np
from exterior_gait import stationary_turn,gaze_rotations,rotations_between,yaw_matrix

class GaitTests(unittest.TestCase):
 def test_never_rewrites_a_translating_actor_transform(self):
  writes=[];actor=SimpleNamespace(set_transform=writes.append)
  for moving,speed in ((True,0.),(True,.85),(False,.12),(False,.85)):
   stationary_turn(actor,carla.Transform(carla.Location(x=3,y=7)),90.,.1,moving,speed)
  self.assertEqual(writes,[])
  stationary_turn(actor,carla.Transform(carla.Location(x=3,y=7)),90.,.1,False,0.)
  self.assertEqual(len(writes),1);self.assertAlmostEqual(writes[0].rotation.yaw,8.5)
  self.assertEqual((writes[0].location.x,writes[0].location.y),(3.,7.))
 def test_visual_gaze_changes_only_mesh_root_without_neck_twists(self):
  names=['crl_root','crl_neck__C','crl_Head__C'];r=np.repeat(np.eye(3)[None,:,:],3,axis=0)
  out=gaze_rotations(names,r,r,150.)
  np.testing.assert_allclose(out[0],yaw_matrix(150.));np.testing.assert_allclose(out[1:],r[1:])
  self.assertAlmostEqual(float(np.linalg.det(out[0])),1.)
 def test_adjacent_gait_rotations_remain_rigid_during_interpolation(self):
  a=np.array([yaw_matrix(0.)]);b=np.array([yaw_matrix(10.)]);out=rotations_between(a,b,.5)
  np.testing.assert_allclose(out[0].T@out[0],np.eye(3),atol=1e-8)
  np.testing.assert_allclose(out[0],yaw_matrix(5.),atol=1e-8)

if __name__=='__main__':unittest.main()
