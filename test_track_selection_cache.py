import unittest
from types import SimpleNamespace as NS
import torch
from track_selection_cache import select_track_parameters

class TrackSelectionCacheTests(unittest.TestCase):
    def setUp(self):
        self.node=NS(training=False,cuboid_tracks=NS(n_tracks=3,tracks_id=['a','b','c']))
        self.params={'positions':torch.arange(18.).reshape(6,3),'gaussian_cuboid_ids':torch.tensor([0,1,2,0,2,1]),'features':torch.arange(30.).reshape(6,5)}
    def edit(self,ids):
        return NS(cuboid_tracks=NS(tracks_id=ids),mapping=torch.tensor([self.node.cuboid_tracks.tracks_id.index(v) for v in ids]))
    def test_exact_subset_and_repeat_reuses_immutable_parameters(self):
        with torch.no_grad():
            a=select_track_parameters(self.node,dict(self.params),self.edit(['b','c']))
            b=select_track_parameters(self.node,dict(self.params),self.edit(['b','c']))
        for key,value in a.items():
            self.assertTrue(torch.equal(value,self.params[key][[1,2,4,5]]));self.assertIs(value,b[key])
    def test_mutated_or_replaced_parameters_invalidate(self):
        with torch.no_grad():
            a=select_track_parameters(self.node,self.params,self.edit(['a']))
            self.params['positions'].add_(1)
            b=select_track_parameters(self.node,self.params,self.edit(['a']))
            self.assertIsNot(a['positions'],b['positions']);self.assertTrue(torch.equal(b['positions'],self.params['positions'][[0,3]]))
            self.params['features']=self.params['features'].clone()
            c=select_track_parameters(self.node,self.params,self.edit(['a']))
            self.assertIsNot(b['positions'],c['positions'])
    def test_actor_set_change_evicts_single_entry_and_live_pose_not_cached(self):
        with torch.no_grad():
            a=select_track_parameters(self.node,self.params,self.edit(['a']))
            b=select_track_parameters(self.node,self.params,self.edit(['c']))
            c=select_track_parameters(self.node,self.params,self.edit(['a']))
        self.assertIsNot(a['positions'],c['positions'])
        self.assertTrue(torch.equal(b['gaussian_cuboid_ids'],torch.tensor([2,2])))
        self.assertEqual(self.node._nurec_track_selection_cache[0][1],('a',))
        self.assertNotIn('poses',c)
    def test_training_or_gradients_are_never_cached(self):
        self.params['positions'].requires_grad_(True)
        a=select_track_parameters(self.node,self.params,self.edit(['a']))
        self.assertIsNone(self.node._nurec_track_selection_cache)
        a['positions'].sum().backward();self.assertEqual(float(self.params['positions'].grad.sum()),6.)
        self.node.training=True
        with torch.no_grad():select_track_parameters(self.node,self.params,self.edit(['a']))
        self.assertIsNone(self.node._nurec_track_selection_cache)
    def test_inference_tensor_without_version_counter_is_not_cached(self):
        with torch.inference_mode():
            params={k:v.clone() for k,v in self.params.items()}
            select_track_parameters(self.node,params,self.edit(['a']))
        self.assertIsNone(self.node._nurec_track_selection_cache)

if __name__=='__main__':unittest.main()
