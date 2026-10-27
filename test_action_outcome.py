import tempfile
import unittest
from pathlib import Path
import numpy as np
from scenario2 import Scenario2
from congestion import Congestion
from fog_trial import DenseFog


class OutcomeFlow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.trials=[]
        self.poses=np.repeat(np.eye(4)[None],101,axis=0);self.poses[:,0,3]=np.arange(101)*10

    def tearDown(self):
        for t in self.trials:t.events.close()
        self.temp.cleanup()

    def trial(self,kind=Scenario2):
        args={'track_id':'7'} if kind is Congestion else {}
        t=kind(self.poses,Path(self.temp.name)/(str(len(self.trials))+'.jsonl'),**args);self.trials.append(t)
        while not t.onset:t.advance(.2,True,[0,0],10)
        t.interaction('open',t.session)
        return t

    def tick(self,t,seconds,speed=10,gap=None,driving=True):
        target=None
        for _ in range(round(seconds/.1)):
            # Model measured ego positions, never set outcome completion flags.
            current_gap=t.desired_gap if gap is None else gap
            xy=[max(0,t.lead_s-t.half_length-1.85-current_gap),0]
            target=t.advance(.1,driving,xy,speed)
        return target

    def test_effect_then_twelve_seconds_then_physical_stop_for_each_profile(self):
        for kind in (Scenario2,Congestion,DenseFog):
            t=self.trial(kind);t.interaction('widen',t.session)
            self.tick(t,2,gap=10)
            self.assertEqual(t.outcome.phase,'applying');self.assertFalse(t.completed)
            self.tick(t,1)
            self.assertEqual(t.outcome.phase,'observing');self.assertFalse(t.completed)
            observed=t.outcome.observed
            self.tick(t,3,driving=False)
            self.assertEqual(t.outcome.observed,observed)
            self.assertEqual(self.tick(t,13),0.)
            self.assertEqual(t.outcome.phase,'stopping');self.assertFalse(t.completed)
            self.tick(t,2,speed=0)
            self.assertTrue(t.completed);self.assertEqual(t.completion_reason,'action_outcome')
            self.assertGreaterEqual(t.outcome.observed,12.)
            self.assertIn('간격',t.outcome.summary)
            self.tick(t,1,speed=0)
            self.assertTrue(t.completed)

    def test_second_action_rejected_and_reset_clears_result(self):
        t=self.trial();t.interaction('horn',t.session)
        with self.assertRaises(ValueError):t.interaction('maintain',t.session)
        t.interaction('close',t.session)
        self.tick(t,14);self.assertEqual(t.outcome.phase,'stopping')
        t.reset();self.assertFalse(t.outcome.active);self.assertFalse(t.completed)

    def test_stop_request_never_claims_verified_shoulder_parking(self):
        t=self.trial(DenseFog);t.interaction('stop_request',t.session)
        self.tick(t,15);self.tick(t,2,speed=0)
        self.assertTrue(t.completed);self.assertEqual(t.outcome.status,'partial')
        self.assertFalse(t.public()['safe_stop_verified']);self.assertFalse(t.action_complete)
        self.assertIn('실행하지 않았습니다',t.outcome.summary)

    def test_unfulfilled_distance_has_honest_timeout_then_observation(self):
        t=self.trial();t.interaction('widen',t.session)
        self.tick(t,46,gap=10)
        self.assertEqual(t.outcome.status,'unfulfilled');self.assertFalse(t.completed)
        self.tick(t,13,gap=10);self.tick(t,2,speed=0,gap=10)
        self.assertTrue(t.completed);self.assertIn('확보하지 못했습니다',t.outcome.summary)

    def test_route_end_does_not_cut_short_action_observation(self):
        t=self.trial();t.interaction('maintain',t.session)
        t.lead_s=t.route.length-8
        self.tick(t,3,speed=0)
        self.assertFalse(t.completed)
        self.tick(t,14,speed=0)
        self.assertTrue(t.completed);self.assertEqual(t.completion_reason,'action_outcome')

if __name__=='__main__':unittest.main()
