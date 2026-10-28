import unittest
from types import SimpleNamespace
import numpy as np
from scene_bridge import Scene

class RouteProjection(unittest.TestCase):
    def timestamp_scene(self, positions, stamps=None):
        scene=object.__new__(Scene)
        scene.route=np.repeat(np.eye(4)[None],len(positions),axis=0)
        scene.route[:,0,3]=positions
        scene.timestamps=np.array(stamps if stamps is not None else [1000000,1100000,1200000])
        scene.start_us=int(scene.timestamps[0]);scene.end_us=int(scene.timestamps[-1]+100)
        return scene

    def transform(self,x,y=.08):
        return SimpleNamespace(location=SimpleNamespace(x=x,y=-y))

    def test_traffic_time_moves_between_sparse_recorded_points(self):
        scene=self.timestamp_scene([0,3,6])
        stamps=[scene.source_timestamp(self.transform(x)) for x in np.linspace(0,3,61)]
        self.assertEqual(stamps[30],1050000)
        self.assertTrue(np.all(np.diff(stamps)>0))
        self.assertLessEqual(max(np.diff(stamps)),1667)
        self.assertEqual(scene.source_timestamp(self.transform(1.5)),stamps[30])

    def test_timestamp_clamps_and_ignores_duplicate_segments(self):
        scene=self.timestamp_scene([0,0,3])
        self.assertEqual(scene.source_timestamp(self.transform(0)),1100000)
        self.assertEqual(scene.source_timestamp(self.transform(1.5)),1150000)
        self.assertEqual(scene.source_timestamp(self.transform(8)),1200000)
        scene.end_us=1200000
        self.assertEqual(scene.source_timestamp(self.transform(8)),1199998)

    def test_time_follows_curved_path_not_world_axis_and_supports_single_pose(self):
        scene=self.timestamp_scene([0,3,3])
        scene.route[:,1,3]=[0,0,4]
        self.assertEqual(scene.source_timestamp(self.transform(3,2)),1150000)
        scene=self.timestamp_scene([0],[1000000])
        self.assertEqual(scene.source_timestamp(self.transform(3)),1000000)

    def test_distance_ignores_along_path_sample_spacing(self):
        scene=object.__new__(Scene)
        scene.route=np.repeat(np.eye(4)[None],3,axis=0)
        scene.route[:,0,3]=[0,3,6]
        transform=SimpleNamespace(location=SimpleNamespace(x=1.5,y=-.08))
        index,distance=scene.nearest(transform)
        self.assertEqual(index,0)
        self.assertAlmostEqual(distance,.08)

    def test_endpoint_distance_and_duplicate_sample(self):
        scene=object.__new__(Scene)
        scene.route=np.repeat(np.eye(4)[None],3,axis=0)
        scene.route[:,0,3]=[0,0,3]
        transform=SimpleNamespace(location=SimpleNamespace(x=-2,y=0))
        self.assertAlmostEqual(scene.nearest(transform)[1],2)

if __name__=='__main__': unittest.main()
