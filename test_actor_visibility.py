import unittest,math
from types import SimpleNamespace as NS
import numpy as np
from actor_visibility import visible_fast_traffic

class ActorVisibilityTests(unittest.TestCase):
    def actor(self,name,point):return NS(track_id=name,pose_pair=NS(start_pose=NS(vec=NS(x=point[0],y=point[1],z=point[2]))))
    def test_only_far_rear_fast_car_is_omitted_and_near_passes_and_blockade_stay(self):
        names=['front','rear','near','lead','truck','unknown']
        actors=[self.actor(n,p) for n,p in zip(names,[[0,0,60],[0,0,-60],[3,0,-2],[0,0,-60],[0,0,-60],[0,0,-60]])]
        specs={n:{'size':[5,2,2]} for n in names if n!='unknown'}
        result=visible_fast_traffic(actors,np.eye(4),math.pi/3,specs,{'lead','truck'})
        self.assertEqual([a.track_id for a in result],['front','near','lead','truck','unknown'])
        self.assertEqual(len(actors),6)
    def test_rotation_is_camera_relative_and_unknown_calibration_fails_open(self):
        a=[self.actor('fast',[60,0,0])];camera=np.eye(4);camera[:3,:3]=[[0,0,1],[0,1,0],[-1,0,0]]
        specs={'fast':{'size':[5,2,2]}}
        self.assertEqual(visible_fast_traffic(a,camera,math.pi/3,specs,set()),a)
        self.assertIs(visible_fast_traffic(a,camera,None,specs,set()),a)

if __name__=='__main__':unittest.main()
