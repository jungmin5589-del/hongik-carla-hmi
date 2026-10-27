"""Clock/pause/end behavior, rather than mirroring controller arithmetic."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from congestion import Congestion


class DurationTrial(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        poses=np.repeat(np.eye(4)[None],730,axis=0)
        poses[:,0,3]=np.arange(730)
        self.s=Congestion(poses,Path(self.tmp.name)/'log.jsonl','7')

    def tearDown(self):
        self.s.events.close();self.tmp.cleanup()

    def test_paused_clock_and_vehicle_stay_put(self):
        for _ in range(200):self.s.advance(.1,True,[0,0],0)
        before=(self.s.elapsed,self.s.lead_s)
        for _ in range(1000):self.s.advance(.1,False,[0,0],0)
        self.assertEqual(before,(self.s.elapsed,self.s.lead_s))

    def test_all_durations_have_stops_and_reach_end_once(self):
        for duration in (300,450,600):
            self.s.set_duration(duration);self.s.reset()
            self.assertTrue(np.all(np.diff(self.s.positions)>=0))
            self.assertGreater(np.sum(self.s.speeds==0),duration*1.5)
            self.assertLess(np.max(self.s.speeds)*3.6,25)
            self.assertAlmostEqual(self.s.positions[-1],self.s.route.length-10)
            self.s.advance(.1,True,[0,0],0)
            self.assertFalse(self.s.completed)
            for _ in range(duration*10+2):
                ego=self.s.lead_s-self.s.half_length-1.85-self.s.desired_gap
                self.s.advance(.1,True,[max(ego,0),0],0)
            self.assertTrue(self.s.completed)
            before=self.s.lead_s
            self.s.advance(.1,True,[ego,0],0)
            self.assertEqual(before,self.s.lead_s)

    def test_horn_does_not_skip_queue_or_change_duration(self):
        for _ in range(201):self.s.advance(.1,True,[0,0],0)
        self.s.interaction('open',self.s.session)
        before=(self.s.lead_s,self.s.duration,self.s.desired_gap)
        self.s.interaction('horn',self.s.session)
        self.assertEqual(before,(self.s.lead_s,self.s.duration,self.s.desired_gap))

    def test_reset_is_new_session_and_validates_duration(self):
        old=self.s.session
        self.s.set_duration(600);self.s.reset()
        self.assertNotEqual(old,self.s.session)
        self.assertEqual(self.s.elapsed,0)
        self.assertEqual(self.s.duration,600)
        with self.assertRaises(ValueError):self.s.set_duration(1)


if __name__=='__main__':unittest.main(verbosity=2)
