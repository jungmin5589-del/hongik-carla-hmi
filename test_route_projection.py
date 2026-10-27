import unittest
from types import SimpleNamespace
import numpy as np
from scene_bridge import Scene

class RouteProjection(unittest.TestCase):
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
