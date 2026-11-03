"""Projection/state invariants; actual native/neural RGB QA is separate."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import carla
from nurec_pedestrian import NightPedestrian, CrossingAdapter
from scenario2 import Route
from hybrid_pedestrian import (MIRROR,OPTICAL_TO_CARLA,optical_pose,
    left_transform,lens_maps,same_background,FramePairs)
from navigation_adapter import NavigationAdapter


class ProjectionTests(unittest.TestCase):
    def test_optical_and_carla_pose_round_trip(self):
        for angles in [(0,0,0),(13,52,-4),(-15,-120,8)]:
            tr=carla.Transform(carla.Location(19,-38,1.6),carla.Rotation(*angles))
            left=np.array(tr.get_matrix());source=optical_pose(np.eye(4),left)
            recovered=MIRROR@source@np.linalg.inv(OPTICAL_TO_CARLA)
            np.testing.assert_allclose(np.array(left_transform(recovered).get_matrix()),left,atol=1e-5)
            self.assertAlmostEqual(np.linalg.det(source[:3,:3]),1.,places=6)

    def test_calibration_scales_to_output_and_preserves_ray_direction(self):
        intrinsic=SimpleNamespace(resolution_w=1920,resolution_h=1080,ftheta_param=SimpleNamespace(
            principal_point_x=960,principal_point_y=540,pixeldist_to_angle_poly=[0,1/1000]))
        u,v,rays,valid=lens_maps(intrinsic,(960,540),(960,540),100)
        self.assertTrue(valid[270,480]);self.assertLess(abs(u[270,480]-480),1)
        self.assertLess(abs(v[270,480]-270),1)
        self.assertGreater(u[270,700],u[270,480]);self.assertGreater(v[400,480],v[270,480])
        np.testing.assert_allclose(np.linalg.norm(rays,axis=-1),1.,atol=2e-7)

    def test_cached_background_cannot_follow_a_moving_camera_or_new_source_time(self):
        p=np.eye(4);self.assertTrue(same_background(p,100000,p,101000))
        self.assertIs(type(same_background(p,100000,p,101000)),bool)
        moved=p.copy();moved[0,3]=.003
        self.assertFalse(same_background(p,100000,moved,100000))
        self.assertFalse(same_background(p,100000,p,103000))

    def test_sensor_pairs_never_mix_frames(self):
        pairs=FramePairs()
        for kind,frame in [('rgb',7),('ids',8),('depth',7)]:pairs.offer(kind,SimpleNamespace(frame=frame))
        self.assertIsNone(pairs.latest)
        pairs.offer('ids',SimpleNamespace(frame=7))
        frame,row,_=pairs.get(.01);self.assertEqual(frame,7)
        self.assertEqual({x.frame for x in row.values()},{7})
        for kind in ('rgb','ids','depth'):pairs.offer(kind,SimpleNamespace(frame=6))
        self.assertEqual(pairs.get(.01)[0],7)


class NightYieldTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();poses=np.repeat(np.eye(4)[None],101,axis=0);poses[:,0,3]=np.arange(101)
        self.sc=NightPedestrian(poses,Path(self.temp.name)/'events.jsonl',{'source-car'})
        self.nav=NavigationAdapter(SimpleNamespace(scenario=self.sc))
    def tearDown(self):self.sc.events.close();self.temp.cleanup()

    def test_route_offset_preserves_carla_right_and_does_not_modify_source(self):
        r=self.sc.crossing_route;xyz,yaw=r.sample(42,3)
        np.testing.assert_allclose(xyz,[42,3,0]);self.assertEqual(yaw,0)
        np.testing.assert_allclose(self.sc.route.points[42],[42,0,0])

    def test_stops_and_requires_explicit_direct_response(self):
        self.sc.advance(.1,False,[32,0],0);self.assertFalse(self.sc.onset)
        self.sc.advance(.1,True,[32,0],0);self.assertTrue(self.sc.onset)
        self.assertEqual(self.sc.target_speed(),0.)
        self.sc.interaction('open',self.sc.session);self.sc.interaction('direct',self.sc.session)
        for _ in range(900):self.sc.advance(.1,True,[32,0],0)
        self.assertEqual(self.sc.phase,'mutual_wait')
        self.sc.complete_direct(self.sc.session);self.sc.advance(.1,True,[32,0],0)
        self.assertEqual(self.sc.phase,'crossing')

    def test_four_choices_and_highbeam_requires_visible_frame_ack(self):
        self.assertEqual([o['action'] for o in self.nav.options()],['study_horn','study_highbeam','study_direct','study_wait'])
        self.sc.advance(.1,True,[32,0],0);self.sc.interaction('open',self.sc.session)
        self.sc.interaction('highbeam',self.sc.session)
        for _ in range(20):self.sc.advance(.1,True,[32,0],0)
        self.assertTrue(self.sc.public()['high_beam']['on'])
        signal=self.sc.high_beam.public();self.sc.high_beam.acknowledge(signal['sequence'],signal['stage'])
        self.sc.advance(.1,True,[32,0],0);self.assertFalse(self.sc.public()['high_beam']['on'])

if __name__=='__main__':unittest.main()
