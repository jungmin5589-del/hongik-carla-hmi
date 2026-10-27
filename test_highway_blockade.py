import tempfile,unittest
import threading,uuid
from types import SimpleNamespace
from pathlib import Path
import numpy as np
from highway_blockade import HighwayBlockade
from navigation_adapter import NavigationAdapter

class FourLaneRules(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();poses=np.repeat(np.eye(4)[None],605,axis=0);poses[:,0,3]=np.arange(605)
        ids=['lead','bus','truck1','truck2']+[str(n) for n in range(12)]
        config=dict(lead_track_id='lead',large_track_ids=ids[1:4],fast_track_ids=ids[4:],
                    vehicles={i:dict(size=[10,3,3.5] if i in ids[1:4] else [4.5,2,1.6]) for i in ids})
        self.t=HighwayBlockade(poses,Path(self.tmp.name)/'events.jsonl',config)

    def tearDown(self):self.t.events.close();self.tmp.cleanup()
    def advance(self,seconds,drive=True):
        for _ in range(round(seconds/.1)):
            ego=max(0,self.t.lead_s-self.t.half_length-1.85-self.t.desired_gap)
            self.t.advance(.1,drive,[ego,0],30)

    def test_variable_speeds_match_actual_pose_displacements(self):
        self.advance(10);seen={}
        for _ in range(240):
            before={s['track_id']:s for s in self.t.traffic_specs()};self.advance(.1)
            after={s['track_id']:s for s in self.t.traffic_specs()}
            for i,s in before.items():
                delta=after[i]['s']-s['s']
                if abs(delta)<10:
                    self.assertAlmostEqual(delta/.1,after[i]['speed'],places=4)
                if s['lane']!=1:
                    seen.setdefault(i,[]).append(s['speed']*3.6)
        for values in seen.values():
            self.assertGreaterEqual(min(values),25-1e-6)
            self.assertLessEqual(max(values),35+1e-6)
            self.assertGreater(max(values)-min(values),9.5)
        self.assertGreater(len({round(s['speed'],2) for s in after.values() if s['lane']!=1}),2)

    def test_three_large_vehicles_do_not_overlap_same_lane(self):
        for _ in range(900):
            large=[s for s in self.t.traffic_specs() if s['role']=='right_large']
            self.assertEqual(len(large),3);self.assertEqual(sorted(s['lane'] for s in large),[3,3,4])
            lane3=sorted(s['s'] for s in large if s['lane']==3)
            self.assertGreaterEqual(lane3[1]-lane3[0],11.8-1e-6)
            self.advance(.1)

    def test_fast_lane_dense_continuous_stream_and_wrap_is_offscreen(self):
        self.advance(10)
        for _ in range(300):
            specs=[s for s in self.t.traffic_specs() if s['role']=='fast_left']
            visible=sorted(s['s'] for s in specs if self.t.ego_s-50<s['s']<self.t.ego_s+100)
            self.assertGreaterEqual(len(visible),4)
            self.assertTrue(all(abs((b-a)-20)<1e-5 for a,b in zip(visible,visible[1:])))
            self.advance(.1)

    def test_pause_reset_and_result_flow(self):
        self.advance(12);before=self.t.public();self.advance(5,False)
        self.assertEqual(self.t.public()['traffic'],before['traffic'])
        self.t.interaction('open',self.t.session);self.t.interaction('maintain',self.t.session)
        self.advance(14);self.assertEqual(self.t.outcome.phase,'stopping')
        for _ in range(20):self.t.advance(.1,True,[self.t.ego_s,0],0)
        self.assertTrue(self.t.completed)
        self.t.reset();self.assertFalse(self.t.outcome.active);self.assertEqual(self.t.elapsed,0)

    def test_highbeam_requires_confirm_and_render_ack_before_result(self):
        self.advance(12);nav=NavigationAdapter(SimpleNamespace(scenario=self.t,lock=threading.Lock(),command={'mode':'auto'}))
        def body(action,**event):return dict(session_id=self.t.session,navigation_id=self.t.session+'-weaving',request_id=uuid.uuid4().hex,action=action,client_event=event)
        self.assertIn('study_highbeam',[o['action'] for o in nav.options()])
        nav.command(body('study_open',options_visible=True))
        nav.command(body('study_choice',choice='study_highbeam'))
        self.assertFalse(self.t.high_beam.public()['on'])
        request=body('study_highbeam');reply=nav.command(request)
        self.assertEqual(nav.command(request),reply);self.assertEqual(self.t.high_beam.count,1)
        self.advance(4);self.assertFalse(self.t.action_complete)
        for stage in range(4):
            self.t.acknowledge_high_beam('old',1,stage)
            self.assertFalse(self.t.high_beam.ack)
            self.t.acknowledge_high_beam(self.t.session,1,stage)
            self.advance(1.2)
        self.assertTrue(self.t.action_complete);self.assertFalse(self.t.high_beam.public()['on'])
        self.assertEqual(self.t.outcome.phase,'observing')
        self.advance(13);self.assertEqual(self.t.outcome.phase,'stopping')
        for _ in range(20):self.t.advance(.1,True,[self.t.ego_s,0],0)
        self.assertTrue(self.t.completed);self.assertIn('상향등',self.t.outcome.summary)
        self.t.reset();self.assertEqual(self.t.high_beam.count,0);self.assertFalse(self.t.high_beam.public()['on'])

if __name__=='__main__':unittest.main()
