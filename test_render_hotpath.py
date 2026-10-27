"""Cached collision offsets must preserve the same CARLA/NuRec alignment."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from scene_bridge import Bridge, MIRROR


class HotPathTests(unittest.TestCase):
    def bridge(self,mode):
        bridge=object.__new__(Bridge)
        bridge.args=SimpleNamespace(proxy_update_mode=mode)
        bridge.track_lock=threading.RLock()
        bridge.scene=SimpleNamespace(alignment=np.eye(4),inverse_alignment=np.eye(4))
        matrix=np.eye(4);matrix[:2,:2]=[[0,-1],[1,0]];matrix[:3,3]=[10,20,3]
        bridge.scenario=SimpleNamespace(lock=threading.RLock(),enabled=True,TRACK_ID='lead',
            pose=lambda:(matrix,0,0),public=lambda:{},SUPPRESS_OTHER_TRAFFIC=True)
        class Actor:
            id=123
            def __init__(self):self.transforms=[]
            @property
            def bounding_box(self):raise AssertionError('A fixed bounding box was queried during a frame.')
            def set_transform(self,tr):self.transforms.append(tr)
        actor=Actor()
        bridge.track_actors=[('lead',actor,np.zeros((2,7)),np.array([0,100]))]
        bridge.track_active={'lead':True};bridge.editable_ids={'lead'}
        bridge.track_bbox_offsets={'lead':np.array([1.,.2,.4])}
        submissions=[]
        bridge.client=SimpleNamespace(apply_batch=lambda commands,tick:submissions.append((commands,tick)))
        return bridge,actor,submissions,matrix

    def check(self,mode):
        bridge,actor,submissions,matrix=self.bridge(mode)
        with patch('scene_bridge.carla.command.ApplyTransform',side_effect=lambda actor_id,tr:SimpleNamespace(actor_id=actor_id,transform=tr)):
            for step in (0.,1.5):
                matrix[0,3]=10.+step
                dynamic,_,_=bridge.update_tracks(50)
                transform=submissions[-1][0][0].transform if mode=='batch' else actor.transforms[-1]
                if mode=='batch':self.assertFalse(submissions[-1][1])
                actual=np.array(transform.get_matrix())@np.r_[bridge.track_bbox_offsets['lead'],1.]
                expected=MIRROR@matrix[:,3]
                np.testing.assert_allclose(actual,expected,atol=1e-5)
                self.assertEqual(dynamic[0].track_id,'lead')
        return actor,submissions

    def test_batch_keeps_fixed_collision_offset_and_tracks_new_positions(self):
        actor,submissions=self.check('batch')
        self.assertEqual(len(submissions),2);self.assertEqual(actor.transforms,[])

    def test_direct_comparison_path_keeps_the_same_alignment(self):
        actor,submissions=self.check('direct')
        self.assertEqual(len(actor.transforms),2);self.assertEqual(submissions,[])


if __name__=='__main__':unittest.main()
