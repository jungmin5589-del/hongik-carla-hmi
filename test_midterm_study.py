"""Request timing, explicit intent and physical-result gates for the midterm UI."""
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from native_carla import StudyNative, NativeNavigation, StudyContext
from midterm_study import OPTIONS,bay_run_in_clear,find_nearby_parking


class MidtermTests(unittest.TestCase):
    def test_bay_rejects_pole_on_approach_even_when_final_bay_is_clear(self):
        route=SimpleNamespace(sample=lambda s,offset:([s,offset,0.],0.))
        self.assertFalse(bay_run_in_clear(route,0.,0.,65.,10.5,[(40.,9.)]))
        self.assertTrue(bay_run_in_clear(route,0.,0.,65.,10.5,[(40.,20.)]))

    def test_parking_relocation_fits_corners_not_just_vehicle_center(self):
        import carla
        road=SimpleNamespace(get_waypoint=lambda q,**kwargs:SimpleNamespace(lane_type=carla.LaneType.Parking) if 1.5<q.y<4.5 else None)
        b=SimpleNamespace(scenario=SimpleNamespace(start_s=5.,base_offset=3.5),
            vehicles=[{'extent':SimpleNamespace(x=2.4,y=1.08)}],world=SimpleNamespace(get_map=lambda:road),
            route=SimpleNamespace(length=100.,sample=lambda s,offset:([s,offset,0.],0.)))
        bay=find_nearby_parking(b)
        self.assertGreater(bay['s'],b.scenario.start_s);self.assertLess(bay['offset'],3.5)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.sc=StudyNative('night',Path(self.temp.name)/'events.jsonl')
        self.b=SimpleNamespace(scenario=self.sc,profile='night',presentation='midterm',condition='B',ego=None)
        self.sc.study.bind(self.b,'B');self.nav=NativeNavigation(self.b)
        self.sc.tick(11,True,30,6.5)

    def tearDown(self):
        self.sc.events.close();self.temp.cleanup()

    def cmd(self,action,**details):
        sid=self.sc.session
        return self.nav.command(dict(session_id=sid,navigation_id=sid+'-weaving',action=action,request_id=uuid.uuid4().hex,client_event=details))

    def select(self,action):
        self.cmd('study_open',options_visible=True);self.cmd('study_choice',choice=action)

    def test_horn_replaces_operator_and_unsafe_overtake(self):
        actions={o['action'] for o in OPTIONS['night']}
        self.assertIn('study_horn',actions);self.assertIn('study_pass',actions)
        self.assertNotIn('study_support',actions);self.assertNotIn('study_overtake',actions)

    def test_congestion_offers_horn_instead_of_truck_spacing(self):
        actions={o['action'] for o in OPTIONS['congestion']}
        self.assertIn('study_horn',actions);self.assertNotIn('study_lateral',actions)
    def test_congestion_merge_ends_without_lateral_target(self):
        self.sc.profile='congestion';self.b.profile='congestion'
        self.select('study_merge');self.cmd('study_merge')
        self.sc.tick(3.1,True,30,5.5);self.sc.study.tick(.1,True)
        self.assertEqual(self.sc.study.phase,'stopping')
        self.assertEqual(self.sc.study.targets(30.,0.),(0.,0.))
        for _ in range(12):self.sc.study.tick(.1,True)
        self.assertTrue(self.sc.completed);self.assertEqual(self.sc.completion_reason,'request_stop')
        self.assertNotEqual(self.sc.study.status,'achieved')

    def test_congestion_horn_executes_once_with_long_audio_duration(self):
        self.sc.profile='congestion';self.b.profile='congestion'
        self.select('study_horn');self.cmd('study_horn')
        self.assertEqual(self.sc.horn_count,1)
        self.assertEqual(self.sc.public()['horn_duration_s'],2.2)
        self.assertEqual(self.sc.study.phase,'applying')
        self.assertEqual(self.sc.study.targets(30.,0.),(0.,0.))
        self.sc.study.tick(.1,True);self.assertFalse(self.sc.completed)
        self.cmd('study_horn_finished');self.assertTrue(self.sc.completed)
        self.assertEqual(self.sc.completion_reason,'horn_audio_finished')
        self.assertEqual(self.sc.study.outcome()['observe_s'],0.)
        self.cmd('study_horn_finished');self.assertEqual(self.sc.horn_count,1)
    def test_opening_ai_does_not_end_or_pause_congestion(self):
        self.sc.profile='congestion';self.b.profile='congestion';self.b.command={'mode':'auto'}
        self.cmd('study_open',options_visible=True)
        self.assertFalse(self.sc.completed);self.assertEqual(self.sc.study.phase,'idle')
        self.assertEqual(self.b.command['mode'],'auto')

    def test_selection_does_not_act_and_countdown_cancel(self):
        self.select('study_horn');self.assertEqual(self.sc.horn_count,0)
        self.cmd('study_horn');self.sc.study.tick(.1,True)
        self.assertEqual(self.sc.horn_count,0)
        self.cmd('study_cancel_pending');self.sc.tick(4,True,30,6.5);self.sc.study.tick(.1,True)
        self.assertEqual(self.sc.horn_count,0);self.assertEqual(self.sc.study.phase,'idle')

    def test_countdown_uses_drive_time_and_executes_once(self):
        self.select('study_horn');self.cmd('study_horn')
        for _ in range(50):self.sc.tick(.1,False,0,6.5);self.sc.study.tick(.1,False)
        self.assertEqual(self.sc.horn_count,0)
        self.sc.tick(3.01,True,30,6.5);self.sc.study.tick(.1,True)
        self.assertEqual(self.sc.horn_count,1)
        for _ in range(10):self.sc.study.tick(.1,True)
        self.assertEqual(self.sc.horn_count,1)

    def test_condition_a_has_only_fixed_requests(self):
        self.b.condition='A';self.sc.study.condition='A'
        self.assertEqual(self.nav.options(),[])
        with self.assertRaises(ValueError):self.select('study_horn')
        self.cmd('study_fixed_help');self.assertEqual(self.sc.study.action,'support')

    def test_widen_requires_measured_gap(self):
        self.select('study_widen');self.cmd('study_widen');self.sc.tick(3.1,True,30,6.5);self.sc.study.tick(.1,True)
        self.assertEqual(self.sc.desired_gap,28)
        self.assertFalse(self.sc.study._ready(20,10)[0]);self.sc.gap=28
        self.assertTrue(self.sc.study._ready(20,10)[0])

    def test_missing_parking_is_partial_never_claims_safe_exit(self):
        self.sc.study.action='end_ride';self.sc.study.safe_bay=None
        self.assertEqual(self.sc.study._ready(0,6),(True,'partial'))
        self.sc.study.status='partial'
        self.assertIn('확인하지 못했어요',self.sc.study.describe())

    def test_highway_stops_wait_at_a_crawl_without_stopping_in_lane(self):
        for profile in ('night','fog','rattle'):
            with self.subTest(profile=profile):
                self.sc.profile=profile;self.b.profile=profile
                study=self.sc.study;study.phase='applying';study.action='safe_stop'
                study.safe_bay={'s':180.,'offset':10.5};study.offset=0.;self.b.ego_s=100.
                with patch('midterm_study.path_to_bay_clear',return_value=False):
                    self.assertEqual(study.targets(30.,0.),(12.,0.))

    def test_blocked_congestion_stop_keeps_rolling_before_shoulder_entry(self):
        self.sc.profile='congestion';self.b.profile='congestion'
        self.b.ego_s=100.;self.b.vehicles=[dict(role='truck',s=102.)]
        study=self.sc.study;study.action='end_ride'
        with patch('midterm_study.find_bay',return_value=dict(s=180.,offset=10.5)):
            study._execute()
        with patch('midterm_study.path_to_bay_clear',return_value=False):
            self.assertEqual(study.targets(30.,0.),(18.,0.))
        self.assertTrue(study.bay_waiting)
        self.b.ego_s=150.
        with patch('midterm_study.path_to_bay_clear',return_value=True),patch('midterm_study.find_bay',return_value=dict(s=225.,offset=10.5)):
            speed,offset=study.targets(30.,0.)
        self.assertGreater(speed,0.);self.assertEqual(offset,0.)
        self.assertEqual(study.safe_bay['s'],225.)
        self.assertEqual(study.bay_start_s,150.)

    def test_inspection_requires_actual_view_exposure(self):
        self.sc.study.action='inspect'
        self.assertFalse(self.sc.study._ready(0,5)[0])
        self.cmd('study_view_opened');self.assertTrue(self.sc.study._ready(0,5)[0])

    def test_stop_request_never_crawls_past_the_stop_point(self):
        study=self.sc.study;study.phase='applying';study.action='safe_stop'
        study.safe_bay={'s':100.,'offset':10.2};study.base_lateral=0.;study.offset=10.2
        self.b.ego_s=108.
        with patch('midterm_study.path_to_bay_clear',return_value=True):
            speed,offset=study.targets(12.,10.2)
        self.assertEqual(speed,0.);self.assertEqual(offset,10.2)

    def test_cancel_after_execution_stops_instead_of_reversing_action(self):
        self.sc.study.phase='observing';self.sc.study.action='horn'
        self.sc.study.cancel()
        self.assertEqual(self.sc.study.phase,'stopping');self.assertEqual(self.sc.study.status,'cancelled')
        self.assertEqual(self.sc.study.targets(30.,0.)[0],0.)

    def paused_actor(self,speed):
        self.b.ego=SimpleNamespace(get_location=lambda:SimpleNamespace(x=0.,y=0.),get_velocity=lambda:SimpleNamespace(length=lambda:speed/3.6))
        self.b.route=SimpleNamespace(sample=lambda s:([0.,0.,0.],0.));self.b.ego_s=0.

    def test_cancelled_stop_finishes_when_paused_and_physically_stationary(self):
        self.paused_actor(0.);self.sc.study.phase='observing';self.sc.study.action='horn';self.sc.study.cancel()
        elapsed=self.sc.elapsed
        for _ in range(12):self.sc.study.tick(.1,False)
        self.assertEqual(self.sc.study.phase,'complete');self.assertTrue(self.sc.completed)
        self.assertEqual(self.sc.study.status,'cancelled');self.assertEqual(self.sc.elapsed,elapsed)

    def test_paused_moving_actor_cannot_claim_stop_complete(self):
        self.paused_actor(5.);self.sc.study.phase='stopping'
        for _ in range(20):self.sc.study.tick(.1,False)
        self.assertFalse(self.sc.completed);self.assertEqual(self.sc.study.stopped,0.)

    def test_paused_stop_without_actor_cannot_finish(self):
        self.sc.study.phase='stopping'
        for _ in range(20):self.sc.study.tick(.1,False)
        self.assertFalse(self.sc.completed)


if __name__=='__main__':unittest.main()
