import math,unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import torch
from background_view_cache import background_view_parameters

class ExpActivation:pass

class BackgroundViewTests(unittest.TestCase):
    def setUp(self):
        self.node=NS(training=False,scale_activation=ExpActivation())
        # A distant front hemisphere and a definitely rear hemisphere.
        front=torch.tensor([[float(i%10)-5,0.,100.+i] for i in range(200)])
        rear=front.clone();rear[:,2]*=-1
        self.p={'positions':torch.cat((front,rear)),'scales':torch.full((400,3),-7.),
            'features_albedo':torch.arange(6000.).reshape(400,5,3)}
        self.rd=NS(sensor_model_parameters=[NS(max_angle=.7)],poses_tquat_startend=torch.tensor([[[0.,0.,0.,0.,0.,0.,1.],[0.,0.,0.,0.,0.,0.,1.]]]))
    def render(self):
        with torch.no_grad():return background_view_parameters(self.node,self.p,self.rd)
    def test_rear_removed_front_and_all_temporal_features_unchanged(self):
        selected=self.render()
        for key in self.p:self.assertTrue(torch.equal(selected[key],self.p[key][:200]))
        self.assertEqual(self.node._nurec_background_view_stats,dict(total=400,kept=200))
    def test_small_motion_reuses_raw_subset_without_freezing_camera(self):
        first=self.render();self.rd.poses_tquat_startend[:,:,:3]+=torch.tensor([1.,0.,0.])
        second=self.render();self.assertIs(first['positions'],second['positions'])
        self.assertEqual(float(self.rd.poses_tquat_startend[0,0,0]),1.)
    def test_large_motion_or_rotation_rebuilds(self):
        first=self.render();self.rd.poses_tquat_startend[:,:,0]=3.
        second=self.render();self.assertIsNot(first['positions'],second['positions'])
        a=.03;self.rd.poses_tquat_startend[:,:,4]=math.sin(a/2);self.rd.poses_tquat_startend[:,:,6]=math.cos(a/2)
        third=self.render();self.assertIsNot(second['positions'],third['positions'])
    def test_mutation_invalidates_and_source_never_modified(self):
        first=self.render()
        self.p['features_albedo'].add_(1)
        second=self.render();self.assertIsNot(first['positions'],second['positions'])
        self.assertTrue(torch.equal(second['features_albedo'],self.p['features_albedo'][:200]))
        self.assertEqual(len(self.p['positions']),400)
    def test_dynamic_training_unknown_lens_or_shutter_changes_fail_open(self):
        for change in ['dynamic','training','lens','shutter']:
            self.setUp()
            if change=='dynamic':self.node.cuboid_tracks=NS()
            elif change=='training':self.node.training=True
            elif change=='lens':self.rd.sensor_model_parameters[0].max_angle=None
            else:self.rd.poses_tquat_startend[0,1,0]=3.
            self.assertIs(self.render(),self.p)
    def test_near_camera_spheres_are_kept_even_behind(self):
        self.p['positions'][200:220]=torch.tensor([0.,0.,-.5])
        selected=self.render();self.assertEqual(len(selected['positions']),220)
    def test_ab_bypass_returns_original_and_releases_subset(self):
        self.render();self.assertIsNotNone(self.node._nurec_background_view_cache)
        with patch('os.path.exists',return_value=True):self.assertIs(self.render(),self.p)
        self.assertIsNone(self.node._nurec_background_view_cache)

if __name__=='__main__':unittest.main()
