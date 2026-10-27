import unittest
from performance_presets import traffic_config

class PerformancePresetTests(unittest.TestCase):
    def config(self):
        names=['lead','t1','t2','t3']+[f'f{i}' for i in range(12)]
        return dict(lead_track_id='lead',large_track_ids=names[1:4],fast_track_ids=names[4:],
            vehicles={n:dict(size=[4,2,2]) for n in names},insert_assets=[dict(id=n) for n in names[1:]])
    def test_compact_retains_critical_traffic_and_only_eight_fast_cars(self):
        original=self.config();result=traffic_config(original,'compact')
        self.assertEqual(len(result['vehicles']),12);self.assertEqual(len(result['fast_track_ids']),8)
        self.assertEqual(result['lead_track_id'],'lead');self.assertEqual(result['large_track_ids'],['t1','t2','t3'])
        self.assertEqual(len(result['insert_assets']),11);self.assertEqual(len(original['vehicles']),16)
        self.assertEqual(set(result['vehicles']),{result['lead_track_id'],*result['large_track_ids'],*result['fast_track_ids']})
    def test_standard_is_unchanged_and_never_aliases_source(self):
        original=self.config();result=traffic_config(original)
        self.assertEqual(result['fast_track_ids'],original['fast_track_ids']);self.assertEqual(len(result['vehicles']),16)
        result['vehicles']['lead']['size'][0]=100;self.assertEqual(original['vehicles']['lead']['size'][0],4)
    def test_invalid_traffic_budget_is_rejected(self):
        with self.assertRaises(ValueError):traffic_config(self.config(),'none')
    def test_compact_scenario_keeps_speed_and_spacing(self):
        import tempfile,numpy as np
        from pathlib import Path
        from highway_blockade import HighwayBlockade
        poses=np.repeat(np.eye(4)[None],250,axis=0);poses[:,0,3]=np.arange(250)
        with tempfile.TemporaryDirectory() as tmp:
            scenario=HighwayBlockade(poses,Path(tmp)/'events.jsonl',traffic_config(self.config(),'compact'))
            try:
                for seconds in [0.,12.,35.,60.]:
                    scenario.elapsed=seconds
                    specs=scenario.traffic_specs();fast=[s for s in specs if s['role']=='fast_left']
                    self.assertEqual(len(specs),12);self.assertEqual(len(fast),8)
                    self.assertTrue(all(s['speed']==25. for s in fast))
                    self.assertTrue(np.allclose(np.diff(sorted(s['s'] for s in fast)),20.))
                self.assertEqual(scenario.large_ids,['t1','t2','t3'])
            finally:scenario.events.close()

if __name__=='__main__':unittest.main()
