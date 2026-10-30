"""Selection semantics, real-state completion gates and pause checks."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from city_scenarios import ContextScenario,OPTIONS
from native_carla import NativeNavigation
from exterior_actor import exterior_target,knock_count
from exterior_dialogue import DIALOGUE,dialogue_cue


class ContextTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.instances=[]
 def tearDown(self):
  for sc in self.instances:sc.events.close()
  self.tmp.cleanup()
 def scene(self,profile):
  sc=ContextScenario(profile,Path(self.tmp.name)/(profile+str(len(self.instances))+'.jsonl'),5.,3.5 if profile=='carpool' else 0.)
  self.instances.append(sc);return sc
 def tick(self,sc,seconds,**kw):
  for _ in range(round(seconds*10)):sc.tick_context(.1,True,kw.get('speed',0.),kw.get('s',5.),kw.get('offset',sc.base_offset),kw.get('actor_clear',False),kw.get('safe',False))
 def test_each_case_has_four_distinct_options(self):
  for p in OPTIONS:
   self.assertEqual(len(OPTIONS[p]),4);self.assertEqual(len({x['scenario_action'] for x in OPTIONS[p]}),4)
 def test_pause_does_not_start_audio_event(self):
  sc=self.scene('carpool')
  for _ in range(1000):sc.tick_context(.1,False,0,5,3.5)
  self.assertEqual(sc.elapsed,0);self.assertFalse(sc.public()['context']['outside_voice_count'])
 def test_relocation_cannot_complete_from_timer_alone(self):
  sc=self.scene('carpool');self.tick(sc,9);sc.interaction('open',sc.session);sc.interaction('relocate',sc.session)
  self.tick(sc,30,actor_clear=True)
  self.assertEqual(sc.outcome.phase,'applying');self.assertFalse(sc.relocation_done)
  self.tick(sc,22,s=11.,actor_clear=True)
  self.assertTrue(sc.completed);self.assertTrue(sc.relocation_done)
 def test_verified_shoulder_stop_requires_actual_location_and_speed(self):
  sc=self.scene('rattle');sc.shoulder_offset=10.2;self.tick(sc,9,speed=18)
  sc.interaction('open',sc.session);sc.interaction('safe_stop',sc.session)
  self.tick(sc,25,speed=0,safe=False)
  self.assertEqual(sc.outcome.phase,'applying')
  self.tick(sc,22,safe=True,offset=10.2)
  self.assertTrue(sc.completed);self.assertEqual(sc.outcome.status,'achieved')
 def test_missing_shoulder_reports_partial_result(self):
  sc=self.scene('rattle');self.tick(sc,9);sc.interaction('open',sc.session);sc.interaction('safe_stop',sc.session)
  self.tick(sc,23)
  self.assertTrue(sc.completed);self.assertEqual(sc.outcome.status,'partial');self.assertIn('아닙니다',sc.summary())
 def test_generic_adapter_executes_only_server_declared_actions(self):
  sc=self.scene('carpool');nav=NativeNavigation(SimpleNamespace(profile='carpool',scenario=sc))
  self.tick(sc,9)
  def command(action,details=None):return nav.command(dict(session_id=sc.session,navigation_id=sc.session+'-weaving',request_id=action,action=action,client_event=details or {}))
  with self.assertRaises(ValueError):command('study_external_notice')
  command('study_open',{'options_visible':True});command('study_choice',{'choice':'study_external_notice'});command('study_external_notice')
  self.assertEqual(sc.last_action,'external_notice');self.assertEqual(sc.announcement_count,1)
 def test_exterior_retreat_overrides_every_loitering_phase(self):
  for elapsed in (0,5,12,19,28,50,82):
   phase,s,offset=exterior_target(elapsed,5.,True)
   self.assertEqual(phase,'leaving');self.assertGreater(s,25.);self.assertGreater(offset,5.)
 def test_door_hits_are_three_irregular_impacts_not_replayed_on_pause(self):
  self.assertEqual([knock_count(t) for t in (0,.74,.76,1.13,1.73,4.9,5.76)],[0,0,1,2,3,3,4])
  sc=self.scene('carpool');self.tick(sc,9);sc.interaction('open',sc.session);sc.interaction('relocate',sc.session)
  self.tick(sc,.1)
  self.assertTrue(sc.actor_retreat,'Move away from the passenger door before the vehicle relocates')
 def test_taxi_dialogue_is_finite_unique_and_stops_on_departure(self):
  self.assertEqual(len({key for _,key,_ in DIALOGUE}),6)
  self.assertEqual(len({text for _,_,text in DIALOGUE}),6)
  self.assertIsNone(dialogue_cue(4.99)['key'])
  self.assertEqual(dialogue_cue(5.)['index'],1)
  self.assertEqual(dialogue_cue(38.)['key'],'city_taxi_plate')
  self.assertIsNone(dialogue_cue(100.)['key'])
  for elapsed in (5,13,24,38,54,72):self.assertIsNone(dialogue_cue(elapsed,True)['key'])

if __name__=='__main__':unittest.main()
