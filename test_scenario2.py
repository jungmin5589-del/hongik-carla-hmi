import tempfile
import unittest
from pathlib import Path
import numpy as np
from scenario2 import Scenario2


class TrialRules(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        matrices = np.repeat(np.eye(4)[None, :, :], 101, axis=0)
        matrices[:, 0, 3] = np.linspace(0, 300, 101)
        self.trial = Scenario2(matrices, Path(self.temp.name) / 'events.jsonl')

    def tearDown(self):
        self.trial.events.close()
        self.temp.cleanup()

    def start_event(self):
        for _ in range(90):
            self.trial.advance(.1, True, [30, 0], 25.)

    def test_pause_freezes_and_actions_require_visible_open_details(self):
        self.trial.advance(1., False, [0, 0], 0.)
        self.assertEqual(self.trial.elapsed, 0.)
        with self.assertRaises(ValueError):
            self.trial.interaction('widen', self.trial.session)
        self.start_event()
        with self.assertRaises(ValueError):
            self.trial.interaction('widen', self.trial.session)
        self.trial.interaction('open', self.trial.session)
        self.trial.interaction('close', self.trial.session)
        self.assertFalse(self.trial.dialog_open)
        self.assertIsNone(self.trial.last_action)

    def test_widen_lowers_target_speed_and_never_teleports_lead(self):
        self.start_event()
        self.trial.gap = 14.
        before_speed = self.trial.target_speed()
        before_pose = self.trial.pose()[0]
        self.trial.interaction('open', self.trial.session)
        self.trial.interaction('widen', self.trial.session)
        self.assertLess(self.trial.target_speed(), before_speed)
        np.testing.assert_allclose(before_pose, self.trial.pose()[0])
        with self.assertRaises(ValueError):
            self.trial.interaction('maintain', self.trial.session)
        self.assertEqual(self.trial.desired_gap, 30.)

    def test_reset_rejects_stale_session_and_weaving_is_bounded(self):
        old = self.trial.session
        self.start_event()
        positions=[]
        for _ in range(150):
            self.trial.advance(.1, True, [70, 0], 20.)
            positions.append(self.trial.pose()[1])
        self.assertLess(min(positions), -1.)
        self.assertGreater(max(positions), 1.)
        self.assertLessEqual(max(abs(p) for p in positions), 1.2)
        self.trial.reset()
        with self.assertRaises(ValueError):
            self.trial.interaction('open', old)

    def test_horn_pose_continuous_and_no_overtake_action(self):
        self.start_event()
        self.trial.interaction('open', self.trial.session)
        before=self.trial.pose()[0]
        self.trial.interaction('horn', self.trial.session)
        np.testing.assert_allclose(before,self.trial.pose()[0])
        self.assertEqual(self.trial.horn_count,1)
        with self.assertRaises(ValueError):
            self.trial.interaction('overtake_right', self.trial.session)

    def test_completion_feedback_waits_for_actual_gap(self):
        self.start_event()
        self.trial.interaction('open', self.trial.session)
        self.trial.interaction('widen', self.trial.session)
        self.assertFalse(self.trial.action_complete)
        self.trial.lead_s = 50.
        self.trial.advance(0.,False,[30,0],10.)
        self.assertFalse(self.trial.action_complete)
        self.trial.advance(0.,False,[10,0],0.)
        self.assertTrue(self.trial.action_complete)
        self.assertIn('넓혔어요',self.trial.feedback)


if __name__ == '__main__':
    unittest.main()
