import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from research_store import ResearchStore,MARKER
from survey_store import save,read,validate,pending,current
from native_carla import finish_emergency

class SurveyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=ResearchStore(Path(self.tmp.name)/'records',start_worker=False)
  self.store.participant('QA-SURVEY');self.sc=NS(session='trial1',elapsed=0.,completed=False,log=lambda *a,**k:None,profile='night')
  self.store.attach(self.sc,'night','AI_ON');self.store.start('trial1');self.sc.elapsed=35;self.sc.completed=True;self.sc.log('trial_completed',reason='action_outcome')
  self.b=NS(scenario=self.sc,research=self.store,experiment_spec={'ai_enabled':True,'practice':False},condition='B',profile='night')
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def answers(self):return dict(anxiety=3,frustration=4,control=5,understanding=6,notice='yes',fit='na',situation='=not a formula')
 def test_draft_and_submission_are_joined_to_the_trial(self):
  save(self.store,'trial1',{'situation':'draft'},True);self.assertTrue(pending(self.b))
  r=save(self.store,'trial1',self.answers(),True,True);self.assertIsNotNone(r['submitted_utc']);self.assertFalse(pending(self.b))
  r2=save(self.store,'trial1',dict(self.answers(),anxiety=7),True,True);self.assertEqual(r2['answers']['anxiety'],3)
  self.assertIn("'=not a formula",self.store.export_csv('surveys').decode('utf-8-sig'));self.assertEqual(self.store.list()['trials'][0]['survey_submitted_utc'],r['submitted_utc'])
 def test_bounds_required_and_unknown_fields(self):
  for values in ({},dict(self.answers(),anxiety=8),dict(self.answers(),control=True),dict(self.answers(),unknown='x')):
   with self.assertRaises(ValueError):save(self.store,'trial1',values,True,True)
 def test_off_omits_ai_questions(self):
  a={k:v for k,v in self.answers().items() if k not in ('notice','fit')};self.assertEqual(validate(a,False,True)['control'],5)
  with self.assertRaises(ValueError):validate(self.answers(),False,True)
 def test_incomplete_or_stale_trial_rejected(self):
  with self.assertRaises(ValueError):current(self.b,{'session_id':'old','answers':self.answers(),'submit':True})
  self.sc.completed=False
  with self.assertRaises(ValueError):current(self.b)
 def test_drive_mirror_contains_survey_and_signal_events(self):
  self.sc.log('vehicle_signal_sample',speed_kph=30.,gap_m=8.,steering_command=.1,request_phase='idle')
  save(self.store,'trial1',self.answers(),True,True)
  target=Path(self.tmp.name)/'drive';target.mkdir();cfg=dict(directory=str(target),folder_id='qa',marker='qa-marker');(target/MARKER).write_text(json.dumps(cfg));self.store.config_path.write_text(json.dumps(cfg))
  self.store.export();self.assertIn('QA-SURVEY',(target/'surveys.csv').read_text('utf-8-sig'));self.assertIn('vehicle_signal_sample',(target/'events.csv').read_text('utf-8-sig'))
  self.assertEqual(json.loads(self.store.detail('trial1')[-1]['details'])['speed_kph'],30.)
 def test_reset_backs_up_then_removes_surveys(self):
  save(self.store,'trial1',self.answers(),True,True);result=self.store.reset('초기화',self.store.list()['counts']);self.assertIsNone(read(self.store,'trial1'));self.assertTrue((Path(result['backup'])/'surveys.csv').exists())
 def test_anonymous_test_stays_out_of_participant_database(self):
  self.sc.research_participant_id=None;r=current(self.b,dict(session_id='trial1',answers=self.answers(),submit=True));self.assertFalse(r['recording']);self.assertIsNone(read(self.store,'trial1'))
 def test_emergency_only_completes_after_physical_stop_once(self):
  logs=[];sc=NS(emergency_requested=True,completed=False,outcome=NS(),study=NS(),log=lambda *a,**k:logs.append(a))
  b=NS(scenario=sc);finish_emergency(b,2.);self.assertFalse(sc.completed);finish_emergency(b,0.);self.assertEqual(sc.completion_reason,'emergency_stop');finish_emergency(b,0.);self.assertEqual(len(logs),1)
if __name__=='__main__':unittest.main()
