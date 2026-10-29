"""Focused checks for physical-trial safety and shared navigation protocol."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from native_carla import NativeScenario, NativeNavigation
from native_carla_route import fog_density


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.sc=NativeScenario('night',Path(self.temp.name)/'events.jsonl')
        self.b=SimpleNamespace(scenario=self.sc,profile='night')
        self.nav=NativeNavigation(self.b)

    def tearDown(self):
        self.sc.events.close();self.temp.cleanup()

    def command(self,action,details=None,session=None,request=None):
        sid=session or self.sc.session
        return self.nav.command(dict(action=action,session_id=sid,navigation_id=sid+'-weaving',
                                     request_id=request or action,client_event=details or {}))

    def test_no_execution_before_explicit_choice(self):
        self.sc.tick(11,True,25,6.5)
        with self.assertRaises(ValueError):self.command('study_distance')
        self.command('study_open',{'options_visible':True})
        with self.assertRaises(ValueError):self.command('study_distance')
        self.command('study_choice',{'choice':'study_distance'})
        self.command('study_distance')
        self.assertEqual(self.sc.desired_gap,28)

    def test_stale_session_and_request_replay(self):
        self.sc.tick(11,True,25,6.5)
        a=self.command('study_open',{'options_visible':True},request='once')
        self.assertEqual(a,self.command('study_open',{'options_visible':True},request='once'))
        with self.assertRaises(ValueError):self.command('study_close',request='once')
        old=self.sc.session;self.sc.reset()
        with self.assertRaises(ValueError):self.command('study_open',session=old)

    def test_result_observation_requires_actual_distance(self):
        self.sc.tick(11,True,25,6.5)
        self.sc.interaction('open',self.sc.session)
        self.sc.interaction('widen',self.sc.session)
        for _ in range(100):self.sc.tick(.1,True,20,7.)
        self.assertEqual(self.sc.outcome.phase,'applying')
        self.assertFalse(self.sc.completed)
        for _ in range(150):self.sc.tick(.1,True,15,28.)
        self.assertEqual(self.sc.outcome.phase,'stopping')
        for _ in range(12):self.sc.tick(.1,True,0,28.)
        self.assertTrue(self.sc.completed)

    def test_pause_does_not_advance_onset(self):
        for _ in range(100):self.sc.tick(.1,False,0,6.5)
        self.assertEqual(self.sc.elapsed,0)
        self.assertFalse(self.sc.onset)

    def test_five_second_fog_onset(self):
        self.assertEqual(fog_density(10),0)
        self.assertEqual(fog_density(15),99)
        values=[fog_density(10+i*.1) for i in range(51)]
        self.assertEqual(values,sorted(values))
        self.assertGreater(fog_density(12.5),40)


if __name__=='__main__':unittest.main()
