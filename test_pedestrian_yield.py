"""State-machine and command tests; actual actor/visual QA is separate."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pedestrian_yield import YieldScenario
from native_carla import NativeNavigation
import carla
import numpy as np
from pedestrian_gesture import swing_between, carla_rotation


class GestureGeometryTests(unittest.TestCase):
    def test_swing_preserves_lengths_and_aligns_joint_direction(self):
        source=np.array([.03,.08,-.25]);target=np.array([.18,.10,-.20])
        rotation=swing_between(source,target)
        np.testing.assert_allclose(rotation@rotation.T,np.eye(3),atol=1e-8)
        np.testing.assert_allclose(rotation@source/np.linalg.norm(source),target/np.linalg.norm(target),atol=1e-8)
        self.assertAlmostEqual(np.linalg.det(rotation),1.)
        np.testing.assert_allclose(swing_between(source,target,0),np.eye(3),atol=1e-8)

    def test_carla_rotation_roundtrip_preserves_its_axis_convention(self):
        for pitch,yaw,roll in [(17,45,35),(-60,150,-25),(77,-100,12)]:
            matrix=np.asarray(carla.Transform(rotation=carla.Rotation(pitch=pitch,yaw=yaw,roll=roll)).get_matrix())[:3,:3]
            restored=np.asarray(carla.Transform(rotation=carla_rotation(matrix)).get_matrix())[:3,:3]
            np.testing.assert_allclose(restored,matrix,atol=1e-6)


class YieldTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.sc=YieldScenario(Path(self.temp.name)/'events.jsonl',SimpleNamespace(cross_s=42.,curb_right=3.,curb_left=-5.))
        self.nav=NativeNavigation(SimpleNamespace(profile='yield',scenario=self.sc))

    def tearDown(self):
        self.sc.events.close();self.temp.cleanup()

    def tick(self,seconds,ego=35.,speed=0.,offset=None):
        for _ in range(round(seconds*10)):self.sc.tick_yield(.1,True,speed,ego,offset)

    def command(self,action,details=None,request=None):
        s=self.sc.session
        return self.nav.command(dict(session_id=s,navigation_id=s+'-weaving',action=action,
                                     request_id=request or action,client_event=details or {}))

    def test_pause_never_advances(self):
        for _ in range(500):self.sc.tick_yield(.1,False,0,35)
        self.assertEqual(self.sc.elapsed,0);self.assertFalse(self.sc.onset)

    def test_explicit_selection_and_replay(self):
        self.tick(1)
        with self.assertRaises(ValueError):self.command('study_horn')
        self.command('study_open',{'options_visible':True})
        with self.assertRaises(ValueError):self.command('study_horn')
        self.command('study_choice',{'choice':'study_horn'})
        first=self.command('study_horn',request='notice-once')
        self.assertEqual(first,self.command('study_horn',request='notice-once'))
        self.assertEqual(self.sc.announcement_count,0)
        self.assertEqual(self.sc.horn_count,1)
        self.tick(8.2)
        self.assertEqual(self.sc.phase,'crossing');self.assertEqual(self.sc.target_speed(),0)

    def test_actual_actor_blocks_release_even_after_long_time(self):
        self.tick(76,offset=3.)
        self.assertEqual(self.sc.phase,'crossing')
        self.tick(80,offset=2.)
        self.assertFalse(self.sc.crossed);self.assertEqual(self.sc.target_speed(),0)
        self.tick(.2,offset=-5.)
        self.assertTrue(self.sc.crossed);self.assertEqual(self.sc.phase,'clearance')
        self.tick(2.2,offset=-5.)
        self.assertEqual(self.sc.phase,'resume');self.assertGreater(self.sc.target_speed(),0)

    def test_no_click_resolves_and_ends_after_actual_resume(self):
        self.tick(75.5)
        self.tick(8.)
        self.tick(3.)
        self.assertEqual(self.sc.phase,'resume')
        self.assertFalse(self.sc.completed)
        self.tick(.2,ego=63,speed=12)
        self.assertEqual(self.sc.phase,'finishing')
        self.tick(2,ego=65)
        self.assertTrue(self.sc.completed)
        self.assertIn('별도 선택 없이',self.sc.feedback)

    def test_support_waits_and_close_never_executes(self):
        self.tick(1)
        self.command('study_open',{'options_visible':True})
        self.command('study_choice',{'choice':'study_direct'})
        self.command('study_close')
        self.assertIsNone(self.sc.last_action)
        with self.assertRaises(ValueError):self.command('study_direct')

    def test_cannot_request_notice_once_crossing_has_started(self):
        self.tick(76)
        self.sc.interaction('open',self.sc.session)
        with self.assertRaises(ValueError):self.sc.interaction('horn',self.sc.session)
        self.assertEqual(self.sc.announcement_count,0)

    def test_direct_response_waits_for_explicit_completion(self):
        self.tick(1)
        self.command('study_open',{'options_visible':True})
        self.command('study_choice',{'choice':'study_direct'})
        self.command('study_direct')
        self.tick(80)
        self.assertTrue(self.sc.direct_pending);self.assertEqual(self.sc.phase,'mutual_wait')
        self.command('study_direct_done')
        self.tick(.2)
        self.assertFalse(self.sc.direct_pending);self.assertEqual(self.sc.phase,'crossing')


if __name__=='__main__':unittest.main()
