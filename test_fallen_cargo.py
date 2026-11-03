"""Decision gates and truthful outcomes without launching the engine."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from fallen_cargo import CargoScenario, cargo_stage, following_speed
from native_carla import NativeNavigation


class CargoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.sc=CargoScenario(Path(self.temp.name)/'events.jsonl')
        self.nav=NativeNavigation(SimpleNamespace(scenario=self.sc,profile='cargo'))

    def tearDown(self):
        self.sc.events.close();self.temp.cleanup()

    def tick(self,seconds=1.,speed=0.,distance=10.,offset=0.,clear=True,driving=True):
        for _ in range(round(seconds/.1)):
            self.sc.tick_cargo(.1,driving,speed,distance,offset,clear)

    def open(self):
        self.sc.release(123)
        self.sc.interaction('open',self.sc.session)

    def test_load_slide_is_continuous_and_starts_before_release(self):
        samples=[cargo_stage(8.8+i*.01) for i in range(121)]
        self.assertEqual(cargo_stage(0),cargo_stage(8.8))
        self.assertGreater(samples[0][0],samples[-1][0])
        self.assertLess(max(abs(b[0]-a[0]) for a,b in zip(samples,samples[1:])),.025)
        self.assertAlmostEqual(cargo_stage(10)[0],cargo_stage(10.001)[0])
        self.assertLessEqual(samples[-1][1],16.)

    def test_closer_following_slowly_matches_truck_and_brakes_when_close(self):
        self.assertEqual(following_speed(25,12),25)
        self.assertLess(following_speed(15,8),15)
        self.assertEqual(following_speed(0,6),0)
        self.assertLessEqual(following_speed(25,40),25)

    def test_notification_and_choice_do_not_execute(self):
        self.open();sid=self.sc.session
        def command(action,details=None):
            return self.nav.command(dict(action=action,session_id=sid,navigation_id=sid+'-weaving',
                                         request_id=action,client_event=details or {}))
        with self.assertRaises(ValueError):command('study_avoid')
        command('study_open',{'options_visible':False})
        command('study_options')
        command('study_choice',{'choice':'study_avoid'})
        self.assertIsNone(self.sc.last_action)
        command('study_avoid')
        self.assertEqual(self.sc.last_action,'avoid')

    def test_pause_does_not_advance_event_or_finish(self):
        self.open();self.sc.interaction('stop',self.sc.session)
        self.tick(20,driving=False)
        self.assertEqual(self.sc.elapsed,0)
        self.assertEqual(self.sc.outcome.phase,'applying')

    def test_avoid_waits_for_space_and_actual_pass(self):
        self.open();self.sc.interaction('avoid',self.sc.session)
        self.tick(6,clear=False)
        self.assertEqual(self.sc.target_offset,0)
        self.assertFalse(self.sc.action_complete)
        self.tick(2,clear=True)
        self.assertEqual(self.sc.target_offset,-3.5)
        self.tick(2,distance=-8,offset=0.)
        self.assertFalse(self.sc.verified_pass)
        self.tick(1,distance=-8,offset=-3.5)
        self.assertTrue(self.sc.verified_pass)
        self.assertEqual(self.sc.outcome.status,'achieved')

    def test_delegate_waits_for_actual_stop(self):
        self.open();self.sc.interaction('delegate',self.sc.session)
        self.tick(6,speed=5.)
        self.assertEqual(self.sc.target_offset,0.)
        self.tick(1,speed=0.)
        self.assertEqual(self.sc.target_offset,-3.5)

    def test_unfulfilled_avoid_is_not_reported_as_success(self):
        self.open();self.sc.interaction('avoid',self.sc.session)
        self.tick(42,clear=False)
        self.assertEqual(self.sc.outcome.status,'unfulfilled')
        self.assertIn('확인하지 못해',self.sc.outcome.summary)

    def test_inspect_requires_stopped_and_applied_zoom(self):
        self.open();self.sc.interaction('inspect',self.sc.session)
        self.tick(6)
        self.assertEqual(self.sc.outcome.phase,'applying')
        self.sc.zoom_applied=True;self.tick(1)
        self.assertEqual(self.sc.outcome.phase,'observing')
        self.tick(12)
        self.assertEqual(self.sc.outcome.phase,'stopping')
        self.tick(1.2)
        self.assertTrue(self.sc.completed)

    def test_collision_is_an_observed_fact_not_a_choice(self):
        self.open();self.sc.interaction('delegate',self.sc.session)
        self.sc.impact_count=1;self.tick(1)
        self.assertEqual(self.sc.target()[0],0)
        self.assertEqual(self.sc.outcome.status,'collision')
        self.assertFalse(self.sc.verified_pass)

    def test_no_unknown_object_drive_over_option(self):
        labels=' '.join(o['label'] for o in self.nav.options())
        self.assertNotIn('밟',labels)
        self.assertEqual(len(self.nav.options()),4)


if __name__=='__main__':unittest.main()
