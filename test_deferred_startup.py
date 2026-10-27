"""Startup must keep driving gated until all protected highway proxies exist."""
import tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
import numpy as np
import scene_bridge
from scene_bridge import Bridge
from highway_blockade import HighwayBlockade

class DeferredStartupTests(unittest.TestCase):
    def check(self,missing=None):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);poses=np.repeat(np.eye(4)[None],250,axis=0);poses[:,0,3]=np.arange(250)
            names=['lead','large1','large2','large3']+[f'fast{i}' for i in range(12)]
            config=dict(lead_track_id='lead',large_track_ids=names[1:4],fast_track_ids=names[4:],vehicles={n:dict(size=[4.,2.,2.]) for n in names})
            scenario=HighwayBlockade(poses,folder/'events.jsonl',config)
            try:
                obj=Bridge.__new__(Bridge);obj.scenario=scenario;obj.run_dir=folder;obj.state={};obj.args=NS(renderer_backend='trained')
                obj.scene=NS(scene_id='synthetic',camera_id='front',start_us=0,end_us=1000000);obj.channel=object()
                obj.high_beam_effect=obj.fog_effect=None;obj.defer_initial_tracks=True;obj.track_actors=[];obj.ready_for_driving=threading.Event();obj.carla_ready_details={'track_actors':0}
                catalog=[NS(id=n,object_size=NS(size_x=4.,size_y=2.,size_z=2.)) for n in names]
                obj.stub=Mock();obj.stub.get_available_cameras.return_value=NS(available_cameras=[NS(logical_id='front',intrinsics=NS())])
                obj.stub.get_server_config.return_value=NS(server_config={'enable_editing_actors':'true','renderer':'default'})
                obj.stub.get_dynamic_objects.return_value=NS(dynamic_objects=catalog)
                events=[]
                obj.warm_renderer_before_proxies=lambda:events.append(('warm',len(obj.track_actors),obj.ready_for_driving.is_set()))
                def spawn():
                    events.append(('spawn',obj.ready_for_driving.is_set()))
                    obj.track_actors=[(n,None,None,None) for n in names if n!=missing]
                obj.setup_tracks=spawn
                with patch.object(scene_bridge.grpc,'channel_ready_future',return_value=Mock()):
                    if missing:
                        with self.assertRaisesRegex(RuntimeError,'Missing highway collision proxies'):obj.connect_renderer()
                        self.assertFalse((folder/'carla-ready.json').exists())
                    else:
                        obj.connect_renderer();self.assertIn('16',(folder/'carla-ready.json').read_text())
                self.assertEqual(events[0],('warm',0,False));self.assertEqual(events[1],('spawn',False))
                self.assertFalse(obj.ready_for_driving.is_set())
            finally:scenario.events.close()
    def test_warmup_precedes_spawn_and_connect_alone_does_not_allow_driving(self):self.check()
    def test_missing_large_vehicle_cannot_be_published_as_ready(self):self.check('large2')
    def test_missing_fast_vehicle_cannot_be_published_as_ready(self):self.check('fast3')

if __name__=='__main__':unittest.main()
