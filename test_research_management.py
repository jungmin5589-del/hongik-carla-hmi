import csv,io,json,sqlite3,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import closing
from research_store import ResearchStore,experiment_date
from research_github import snapshot,upload
class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=ResearchStore(Path(self.temp.name),start_worker=False)
        self.store.participant('참가자 이름');sc=SimpleNamespace(session='test',elapsed=0.,log=lambda *a,**k:None)
        self.store.attach(sc,'congestion','B');self.store.start('test');sc.log('scenario_onset')
    def tearDown(self):self.store.close();self.temp.cleanup()
    def test_date_is_experiment_date_in_seoul(self):
        self.assertEqual(experiment_date('2026-11-10T16:00:00+00:00'),'2026-11-11')
        self.assertIn('experiment_date',self.store.export_csv().decode('utf-8-sig'))
    def test_reset_requires_confirmation_and_current_counts(self):
        counts=self.store.list()['counts']
        for token,expected in [('',counts),('초기화',{})]:
            with self.assertRaises(ValueError):self.store.reset(token,expected)
        result=self.store.reset('초기화',counts)
        self.assertEqual(self.store.list()['counts']['participants'],0)
        self.assertIsNone(self.store.current_participant())
        with closing(sqlite3.connect(Path(result['backup'])/'research.sqlite3')) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM participants').fetchone()[0],1)
    def test_snapshot_preserves_names_and_dates_and_only_exports_csv_json(self):
        files,meta=snapshot(self.store)
        self.assertTrue(meta['includes_participant_names'])
        self.assertTrue(all(Path(p).suffix in ('.csv','.json') for p in files))
        data=next(v for p,v in files.items() if p.endswith('trials.csv')).decode('utf-8-sig')
        self.assertIn('참가자 이름',data);self.assertIn(meta['experiment_dates'][0],data)
    def test_public_upload_uses_separate_data_branch_and_named_snapshot(self):
        commands=[]
        def runner(args,**kwargs):commands.append(args);return SimpleNamespace(returncode=0,stdout=b'fake-commit' if 'rev-parse' in args else b'')
        files,meta=snapshot(self.store);result=upload(self.store,files,meta,runner)
        self.assertEqual(result['state'],'uploaded');self.assertTrue(result['url'].endswith('/research-data'))
        self.assertTrue(any('HEAD:refs/heads/research-data' in c for c in commands))
        self.assertFalse(any('--force' in c for c in commands))
