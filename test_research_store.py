import json,sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from research_store import ResearchStore,MARKER

class ResearchTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=ResearchStore(self.root/'local',start_worker=False)
 def tearDown(self):self.store.close();self.temp.cleanup()
 def trial(self,name='P001'):
  self.store.participant(name);sc=SimpleNamespace(session='session1',elapsed=0,log=lambda *a,**k:None)
  self.store.attach(sc,'night','B','zh');self.store.start(sc.session);return sc
 def test_choice_times_are_relative_to_start_and_onset_and_cancellations_remain(self):
  sc=self.trial();sc.elapsed=10;sc.log('scenario_onset');sc.elapsed=17.25;sc.log('navigation_study_choice',client_event={'choice':'study_horn','device':'must-not-export'})
  sc.elapsed=18;sc.log('navigation_study_cancel');sc.elapsed=20;sc.log('navigation_study_choice',client_event={'choice':'study_widen'})
  sc.elapsed=21;sc.log('navigation_execution_confirmed',action='study_widen');sc.elapsed=36;sc.log('request_completed',action='widen',status='achieved')
  data=self.store.list();row=data['trials'][0]
  self.assertEqual(row['participant_name'],'P001');self.assertEqual(row['selected_s'],17.25);self.assertEqual(row['selected_after_onset_s'],7.25)
  self.assertEqual(row['selection_count'],2);self.assertEqual(row['executed_s'],21);self.assertEqual(row['result'],'achieved');self.assertEqual(row['language'],'zh')
  events=self.store.detail(sc.session);self.assertIn('navigation_study_cancel',[e['event'] for e in events]);self.assertNotIn('must-not-export',json.dumps(events))
 def test_reset_exports_after_releasing_record_lock(self):
  from unittest.mock import patch
  self.trial();counts=self.store.list()['counts']
  def unlocked_export():self.assertFalse(self.store.lock._is_owned())
  with patch.object(self.store,'export',side_effect=unlocked_export):
   result=self.store.reset('초기화',counts)
  self.assertTrue(result['reset']);self.assertEqual(self.store.list()['counts']['trials'],0)
 def test_unregistered_development_sessions_are_not_participant_records(self):
  self.store.attach(SimpleNamespace(session='dev'),'night','B');self.assertEqual(self.store.list()['counts']['trials'],0)
 def test_unicode_names_survive_restart_and_csv_is_excel_safe(self):
  self.trial('=测试姓名');text=self.store.export_csv().decode('utf-8-sig');self.assertIn("'=测试姓名",text)
  again=ResearchStore(self.store.root,start_worker=False)
  try:self.assertEqual(again.list()['trials'][0]['participant_name'],'=测试姓名');self.assertIsNone(again.current_participant())
  finally:again.close()
 def test_drive_target_requires_exact_private_folder_marker(self):
  target=self.root/'drive';target.mkdir();config={'folder_id':'folder','marker':'correct','directory':str(target)}
  self.store.config_path.write_text(json.dumps(config));(target/MARKER).write_text(json.dumps({'folder_id':'different','marker':'correct'}))
  self.trial();self.store.export();self.assertFalse((target/'research.sqlite3').exists());self.assertEqual(self.store.sync_status()['state'],'waiting-for-drive-desktop')
  (target/MARKER).write_text(json.dumps({'folder_id':'folder','marker':'correct'}));self.store.export()
  self.assertTrue((target/'trials.csv').is_file())
  with closing(sqlite3.connect(target/'research.sqlite3')) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM participants').fetchone()[0],1)
  self.store.participant('P002');self.store.export()
  with closing(sqlite3.connect(target/'research.sqlite3')) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM participants').fetchone()[0],2)
 def test_names_cannot_be_empty_or_control_text(self):
  for name in ('','   ','a\nb','x'*81):
   with self.assertRaises(ValueError):self.store.participant(name)

class AsyncResearchTests(unittest.TestCase):
 def test_recording_queue_does_not_wait_for_export_lock_and_keeps_event_time(self):
  import threading,time
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder:
   store=ResearchStore(Path(folder))
   try:
    store.participant('QA');sc=SimpleNamespace(session='async1',elapsed=0.,log=lambda *args,**kwargs:None)
    store.attach(sc,'night','B');store.start(sc.session);store.heartbeat[sc.session]=100.
    store.lock.acquire()
    returned=threading.Event()
    def emit():
     with patch('research_store.time.monotonic',return_value=111.):
      sc.elapsed=10.;sc.log('scenario_onset')
     returned.set()
    thread=threading.Thread(target=emit);thread.start()
    try:self.assertTrue(returned.wait(.5),'controller event emission must not wait on DB/export lock')
    finally:store.lock.release()
    thread.join();store.flush_events();row=store.detail(sc.session)[0]
    self.assertEqual(row['elapsed_s'],10.);self.assertEqual(row['wall_since_start_s'],11.)
   finally:store.close()

if __name__=='__main__':unittest.main()
