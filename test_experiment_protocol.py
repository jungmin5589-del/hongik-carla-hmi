"""Protocol and request integration. These are fixtures, not live road validation."""
import tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from native_carla import StudyNative,NativeNavigation
from experiment_protocol import spec,options,intent,traffic_targets
from experiment_api import request

class ProtocolTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.sc=StudyNative('night',Path(self.tmp.name)/'events.jsonl')
  self.b=NS(scenario=self.sc,profile='night',presentation='midterm',condition='B',experiment_spec=spec(4),lock=threading.RLock(),ego=None,state={},command={'mode':'auto'})
  self.sc.study.bind(self.b,'B');self.nav=NativeNavigation(self.b);self.sc.tick(11,True,30,6.5)
 def tearDown(self):self.sc.events.close();self.tmp.cleanup()
 def req(self,text,execute=False,**extra):return request(self.b,dict(session_id=self.sc.session,text=text,execute=execute,**extra))
 def test_proposal_never_executes(self):
  r=self.req('앞차랑 거리 더 넓혀 줘');self.assertEqual(r['action'],'widen');self.assertEqual(self.sc.study.phase,'idle')
  self.req('앞차랑 거리 더 넓혀 줘',True);self.assertEqual(self.sc.study.phase,'queued')
 def test_direct_request_executes_without_a_fake_dialog_exposure_timestamp(self):
  self.assertIsNone(self.sc.detail_opened)
  self.req('앞차랑 거리 더 넓혀 줘',True);self.sc.study._execute()
  self.assertEqual(self.sc.desired_gap,6.5);self.assertEqual(self.sc.study.gap_goal,28.)
  self.assertEqual(self.sc.study.phase,'applying');self.assertIsNone(self.sc.detail_opened)
  self.assertFalse(self.sc.dialog_open)
 def test_stale_session_rejected(self):
  with self.assertRaises(ValueError):request(self.b,dict(session_id='old',text='경적 울려 줘',execute=True))
 def test_off_has_no_actions_or_passive_ai_copy(self):
  self.b.experiment_spec=spec(3);self.b.condition='A';self.sc.study.bind(self.b,'A')
  d=dict(connected=True,session={'navigation':{'research_event':{'narration':{'url':'secret'}}}},passive={'title':'AI state'})
  d=self.sc.study.protocol.enrich(d);self.assertFalse(d['session']['navigation']['research_event']['active']);self.assertEqual(d['passive'],{});self.assertEqual(self.nav.options(),[])
  with self.assertRaises(ValueError):self.req('경적 울려 줘',True)
 def test_practice_only_changes_display_temperature(self):
  self.b.experiment_spec=spec(0);self.sc.study.bind(self.b,'B')
  self.assertFalse(self.req('경적 울려 줘',True)['supported'])
  self.req('온도를 22도로 해 줘',True);self.assertEqual(self.sc.study.protocol.temperature,22);self.assertEqual(self.sc.horn_count,0)
 def test_practice_finishes_through_a_physical_stop(self):
  self.b.experiment_spec=spec(0);self.sc.study.bind(self.b,'B');self.sc.elapsed=120
  self.sc.study.protocol.tick(.1,True)
  self.assertEqual(self.sc.study.phase,'stopping');self.assertFalse(self.sc.completed)
  self.assertEqual(self.sc.study.targets(30.,0.)[0],0.)
 def test_maintain_and_explain_do_not_end_trial(self):
  self.req('그냥 유지할게',True);self.req('왜 이렇게 가?',True)
  self.assertEqual(self.sc.study.phase,'idle');self.assertFalse(self.sc.completed)
 def test_watch_waits_for_changed_state_and_twenty_seconds_after_notice(self):
  p=self.sc.study.protocol;self.req('위험해지면 알려 줘',True)
  self.b.vehicles=[{'extent':NS(x=2.)},{'s':11.,'extent':NS(x=2.),'offset':1.6}];self.b.ego_s=0
  for _ in range(20):self.sc.elapsed+=.1;p.tick(.1,True)
  self.assertFalse(p.notified);self.assertEqual(self.sc.study.phase,'idle')
  self.b.vehicles[1]['offset']=2.2
  for _ in range(16):self.sc.elapsed+=.1;p.tick(.1,True)
  self.assertTrue(p.notified);self.assertEqual(self.sc.study.phase,'idle')
  self.sc.elapsed+=19;p.tick(.1,True);self.assertEqual(self.sc.study.phase,'idle')
  self.sc.elapsed+=2;p.tick(.1,True);self.assertEqual(self.sc.study.phase,'stopping')
 def test_new_request_supersedes_monitor_timer(self):
  p=self.sc.study.protocol;self.req('위험해지면 알려 줘',True);p.notified=True;p.notify_at=self.sc.elapsed
  self.req('경적 울려 줘',True);self.sc.elapsed+=30;p.tick(.1,True)
  self.assertFalse(p.watch);self.assertEqual(self.sc.study.action,'horn');self.assertEqual(self.sc.study.phase,'queued')
 def test_options_match_engine_and_keep_maintain(self):
  self.assertEqual({x['action'] for x in self.nav.options()},{'study_notify','study_widen','study_pass','study_horn','study_maintain'})
  self.assertNotEqual(options('night',0)[0],options('night',1)[0])
 def test_negative_or_unsupported_requests_do_not_move_vehicle(self):
  for text in ('경적 울리지 말고 기다려','앞차와 거리 좁혀 줘','다른 출구로 가 줘'):
   self.assertIsNone(intent(text,'night'))
 def test_same_smooth_physics_for_on_and_off(self):
  self.assertEqual(traffic_targets('night',5),(30.,0.));self.assertEqual(traffic_targets('night',55,True),(30.,0.))
  self.assertGreater(traffic_targets('congestion',10)[0],traffic_targets('congestion',40)[0])
  for t in (10,15,25,30,40,45):self.assertLess(abs(traffic_targets('night',t+.001)[1]-traffic_targets('night',t-.001)[1]),.01)
 def test_disconnected_state_is_safe(self):self.assertEqual(self.sc.study.protocol.enrich({'connected':False}),{'connected':False})

if __name__=='__main__':unittest.main()
