"""Research actions must remain explicit, session-bound, and idempotent."""
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from navigation_adapter import NavigationAdapter
from scenario2 import Scenario2


class NavigationSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        poses = np.repeat(np.eye(4)[None], 101, axis=0)
        poses[:,0,3] = np.arange(101)
        self.sc = Scenario2(poses, Path(self.temp.name)/'events.jsonl')
        self.sc.advance(7., True, [0.,0.], 0.)
        # Advance clips long dt to .2s, so exercise the real onset path.
        for _ in range(31): self.sc.advance(.2,True,[0.,0.],0.)
        self.nav = NavigationAdapter(SimpleNamespace(scenario=self.sc,lock=threading.Lock(),command={'mode':'auto'}))

    def tearDown(self):
        self.sc.events.close(); self.temp.cleanup()

    def body(self, action, **event):
        return dict(session_id=self.sc.session,navigation_id=self.sc.session+'-weaving',
                    request_id=uuid.uuid4().hex,action=action,client_event=event)

    def choose(self, action):
        self.nav.command(self.body('study_open'))
        self.nav.command(self.body('study_options'))
        self.nav.command(self.body('study_choice',choice=action))

    def test_inspection_does_not_act(self):
        self.choose('study_distance')
        self.assertEqual(self.sc.desired_gap,self.sc.BASE_GAP)
        self.assertIsNone(self.sc.last_action)

    def test_execute_once_and_reply_is_session_bound(self):
        self.choose('study_horn'); body=self.body('study_horn')
        result=self.nav.command(body)
        self.assertEqual(self.nav.command(body),result)
        self.assertEqual(self.sc.horn_count,1)
        self.assertTrue(self.nav.reply(self.sc.session,result['command_id'])['accepted'])
        self.assertFalse(self.nav.reply('old',result['command_id'])['accepted'])

    def test_cancel_and_close_prevent_execution(self):
        self.choose('study_distance'); self.nav.command(self.body('study_cancel'))
        with self.assertRaises(ValueError): self.nav.command(self.body('study_distance'))
        self.nav.command(self.body('study_choice',choice='study_distance'))
        self.nav.command(self.body('study_close'))
        with self.assertRaises(ValueError): self.nav.command(self.body('study_distance'))
        self.assertEqual(self.sc.desired_gap,self.sc.BASE_GAP)

    def test_old_session_cannot_act(self):
        self.choose('study_horn'); old=self.body('study_horn'); self.sc.reset()
        with self.assertRaises(ValueError): self.nav.command(old)
        self.assertEqual(self.sc.horn_count,0)

    def test_maintain_preserves_requested_distance(self):
        self.choose('study_distance'); self.nav.command(self.body('study_distance'))
        with self.assertRaises(ValueError):self.choose('study_wait')
        self.assertEqual(self.sc.desired_gap,self.sc.WIDE_GAP)

    def test_one_click_exposes_choices_but_never_executes(self):
        self.nav.command(self.body('study_open',options_visible=True))
        self.assertTrue(self.nav.options_open)
        self.assertIsNone(self.sc.last_action)
        self.assertEqual(self.sc.horn_count,0)
        with self.assertRaises(ValueError):self.nav.command(self.body('study_horn'))
        self.nav.command(self.body('study_choice',choice='study_horn'))
        self.assertEqual(self.sc.horn_count,0)
        self.nav.command(self.body('study_horn'))
        self.assertEqual(self.sc.horn_count,1)

    def test_inactive_and_completed_cannot_offer_or_execute(self):
        self.sc.reset()
        self.nav.command(self.body('study_open',options_visible=True))
        self.assertFalse(self.nav.options_open)
        with self.assertRaises(ValueError):self.nav.command(self.body('study_choice',choice='study_horn'))
        for _ in range(32):self.sc.advance(.2,True,[0.,0.],0.)
        self.nav.command(self.body('study_open',options_visible=True))
        self.nav.command(self.body('study_choice',choice='study_horn'))
        self.sc.completed=True
        with self.assertRaises(ValueError):self.nav.command(self.body('study_horn'))
        self.assertEqual(self.sc.horn_count,0)


if __name__ == '__main__': unittest.main(verbosity=2)
