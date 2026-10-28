"""Synthetic regression checks for the straight-ego study stimulus."""
import math
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

import numpy as np

from launch_live import can_reuse_drive
from navigation_adapter import NavigationAdapter
from night_weaving import BoundaryWeaving, recorded_track_height
from profile_sources import source_id


class StraightWeavingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.route = np.repeat(np.eye(4)[None], 201, axis=0)
        self.route[:,0,3] = np.linspace(0,600,201)
        self.trial = BoundaryWeaving(self.route, Path(self.temp.name)/'events.jsonl')

    def tearDown(self):
        self.trial.events.close()
        self.temp.cleanup()

    def test_close_gap_on_start_and_reset_uses_actual_selected_car_length(self):
        self.assertEqual(self.trial.gap,5.5)
        self.assertAlmostEqual(self.trial.lead_s-self.trial.half_length-1.85,5.5)
        self.trial.half_length=2.5
        self.trial.reset()
        self.assertEqual(self.trial.desired_gap,5.5)
        self.assertAlmostEqual(self.trial.lead_s-self.trial.half_length-1.85,5.5)

    def test_widen_retains_real_distance_response_from_close_baseline(self):
        self.trial.onset=True
        self.trial.onset_monotonic=0.
        self.trial.interaction('open',self.trial.session)
        before=self.trial.pose()[0].copy()
        self.trial.interaction('widen',self.trial.session)
        self.assertEqual(self.trial.desired_gap,28.)
        self.assertEqual(self.trial.target_speed(),0.)
        self.assertFalse(self.trial.action_complete)
        np.testing.assert_allclose(self.trial.pose()[0],before)

    def test_stays_across_the_boundary_after_smooth_onset(self):
        samples = []
        for _ in range(450):
            self.trial.advance(.1,True,[0.,0.],10.)
            if self.trial.elapsed >= 10.:
                _, lateral, yaw = self.trial.pose()
                samples.append(lateral)
                self.assertLess(abs(lateral-self.trial.BOUNDARY), .9)
                self.assertLess(abs(yaw),.3)
        self.assertLess(min(samples),-2.3)
        self.assertGreater(max(samples),-1.3)
        self.assertEqual(self.trial.ego_s,0.)

    def test_no_jump_at_onset_and_pause_preserves_pose(self):
        self.trial.elapsed=5.99
        self.assertEqual(self.trial.pose()[1],0.)
        self.trial.advance(.02,True,[0.,0.],10.)
        self.assertLess(abs(self.trial.pose()[1]),.001)
        pose=self.trial.pose()[0].copy()
        self.trial.advance(1.,False,[0.,0.],0.)
        np.testing.assert_allclose(self.trial.pose()[0],pose)

    def adapter(self):
        transform=SimpleNamespace(location=SimpleNamespace(x=0.,y=0.,z=1.),rotation=SimpleNamespace(yaw=0.))
        bridge=SimpleNamespace(scenario=self.trial,lock=threading.Lock(),command={'mode':'paused'},
            ego=SimpleNamespace(id=1,get_transform=lambda:transform),track_actors=[],
            state=dict(phase='live',speed_kph=0.,mode='paused',width=960,height=540),
            scene=SimpleNamespace(route=self.route),world=SimpleNamespace(get_snapshot=lambda:SimpleNamespace(frame=1)))
        return NavigationAdapter(bridge)

    def test_study_has_no_crash_or_overtake_option_and_map_matches_lane(self):
        nav=self.adapter()
        self.assertEqual([o['action'] for o in nav.options()],['study_horn','study_distance','study_wait'])
        state=nav.state()
        self.assertEqual(state['ego']['lane_index'],1)
        left,right=state['road']['lanes']
        self.assertAlmostEqual(left['points'][0]['right_m'],0.)
        self.assertAlmostEqual(right['points'][0]['right_m'],3.6)
        self.assertNotIn('crash',self.trial.public())
        self.assertFalse(getattr(self.trial,'OVERTAKE_TRIAL',False))

    def test_launcher_rejects_legacy_or_crash_night_mode(self):
        state=dict(profile='night',scene_id=source_id('night'),phase='live',error=None,renderer_backend='trained')
        self.assertFalse(can_reuse_drive(state,'night'))
        self.assertFalse(can_reuse_drive(dict(state,night_mode='overtake-crash'),'night'))
        self.assertTrue(can_reuse_drive(dict(state,night_mode='straight'),'night'))
        self.assertTrue(can_reuse_drive(dict(state,night_mode='overtake-crash'),'night',night_mode='overtake-crash'))

    def test_heading_follows_actual_lateral_motion(self):
        self.trial.onset=True
        for time in [6.5,8.,10.,14.,19.,25.,31.]:
            self.trial.elapsed=time-.001;before=self.trial.pose()[1]
            self.trial.elapsed=time+.001;after=self.trial.pose()[1]
            self.trial.elapsed=time;yaw=self.trial.pose()[2]
            self.assertAlmostEqual(math.tan(yaw)*self.trial.LEAD_SPEED,(after-before)/.002,places=4)

    def test_grounding_uses_native_height_instead_of_half_vehicle_height(self):
        native=np.repeat(np.eye(4)[None],5,axis=0)
        native[:,0,3]=[20.,30.,40.,50.,60.]
        native[:,2,3]=[.4,.42,.41,.39,10.]
        self.assertAlmostEqual(recorded_track_height(self.trial.route,native),.41)


if __name__=='__main__':unittest.main(verbosity=2)
