import unittest
from types import SimpleNamespace as NS
import torch
from lean_runtime import compact_static_background

class StaticLODTests(unittest.TestCase):
    def test_only_faint_background_is_removed_once_and_fields_stay_aligned(self):
        class Node(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.positions=torch.nn.Parameter(torch.arange(600.).reshape(200,3))
                self.densities=torch.nn.Parameter(torch.cat((torch.full((20,1),-7.),torch.full((180,1),1.))))
                self.features_albedo=torch.nn.Parameter(torch.arange(600.).reshape(200,3))
            def get_parameters(self):return dict(self.named_parameters())
        node=Node();road=Node();car=Node();car.cuboid_tracks=NS()
        model=NS(gaussians_nodes=torch.nn.ModuleDict(dict(background=node,road=road,cars=car)))
        original=node.positions.detach().clone();road_id=id(road.positions);car_id=id(car.positions)
        compact_static_background(model)
        self.assertTrue(torch.equal(node.positions,original[20:]))
        self.assertTrue(torch.equal(node.features_albedo,original[20:]))
        self.assertEqual((id(road.positions),id(car.positions)),(road_id,car_id))
        first=id(node.positions);compact_static_background(model)
        self.assertEqual(id(node.positions),first)
        self.assertEqual(model._nurec_background_lod['kept'],180)
    def test_suspicious_mass_removal_and_dynamic_background_fail_open(self):
        class Node(torch.nn.Module):
            def __init__(self):
                super().__init__();self.positions=torch.nn.Parameter(torch.zeros(200,3));self.densities=torch.nn.Parameter(torch.full((200,1),-8.))
            def get_parameters(self):return dict(self.named_parameters())
        for dynamic in [False,True]:
            node=Node()
            if dynamic:node.cuboid_tracks=NS()
            model=NS(gaussians_nodes={'background':node});original=node.positions
            compact_static_background(model);self.assertIs(node.positions,original)

if __name__=='__main__':unittest.main()
