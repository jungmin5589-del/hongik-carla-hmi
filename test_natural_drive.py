"""Source-pose preservation and transitions; no GPU/image-quality assertions."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.spatial.transform import Rotation
from natural_drive import NaturalDrive,RecordedCamera,RecordedTraffic
from navigation_adapter import NavigationAdapter
from launch_live import can_reuse_drive
from profile_sources import source_id
from unittest.mock import Mock,patch
from scene_bridge import Bridge

class NaturalTests(unittest.TestCase):
    def route(self):
        poses=np.repeat(np.eye(4)[None],4,axis=0);poses[:,0,3]=[0,250,500,750];return poses
    def trial(self,profile='fog'):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        sc=NaturalDrive(profile,self.route(),Path(directory.name)/'events.jsonl',{'7','36'})
        self.addCleanup(sc.events.close);return sc
    def test_original_actor_interpolation_and_temporal_visibility(self):
        q=Rotation.from_euler('z',[[0],[90]],degrees=True).as_quat()
        poses=np.column_stack(([[1,2,3],[11,4,5]],q))
        traffic=RecordedTraffic(dict(tracks_id=[36],tracks_label_class=['automobile'],tracks_poses=[poses],tracks_timestamps_us=[[1000000,2000000]]),np.eye(4))
        self.assertEqual(traffic.sample(999999),{})
        pose=traffic.sample(1500000)['36'];np.testing.assert_allclose(pose[:3,3],[6,3,4])
        self.assertAlmostEqual(Rotation.from_matrix(pose[:3,:3]).as_euler('xyz',degrees=True)[2],45)
        self.assertEqual(traffic.sample(2000001),{})
    def test_camera_preserves_rig_near_path_but_not_off_route(self):
        poses=self.route();cam=RecordedCamera(poses,[0,100,200,300]);actual=cam.sample(50);actual[1,3]=.1
        near,diag=cam.stabilize(actual,50);self.assertEqual(diag['physical_weight'],0)
        np.testing.assert_allclose(near[:3,3],[125,0,0])
        actual[1,3]=2;far,diag=cam.stabilize(actual,50);self.assertEqual(diag['physical_weight'],1)
        np.testing.assert_allclose(far,actual)
    def test_no_inserted_lead_pause_and_fog_ramp(self):
        sc=self.trial();self.assertIsNone(sc.pose()[0]);self.assertFalse(hasattr(sc,'insert_asset_specs'))
        sc.advance(.2,False,[0,0],0);self.assertEqual(sc.elapsed,0)
        for _ in range(51):sc.advance(.2,True,[0,0],9)
        self.assertTrue(sc.onset)
        for _ in range(25):sc.advance(.2,True,[0,0],9)
        self.assertAlmostEqual(sc.public()['fog']['beta'],.2)
    def test_stop_partial_not_verified_pull_over(self):
        sc=self.trial('rattle')
        for _ in range(45):sc.advance(.2,True,[0,0],9)
        sc.interaction('open',sc.session);sc.interaction('stop_request',sc.session)
        for _ in range(200):sc.advance(.2,True,[0,0],0)
        self.assertTrue(sc.completed);self.assertEqual(sc.outcome.status,'partial')
        self.assertFalse(sc.public()['safe_stop_verified']);self.assertIn('아닙니다',sc.feedback)
        self.assertIn('부분적으로',sc.public()['outcome']['message'])
    def test_duration_end_has_navigation_end_message(self):
        sc=self.trial();sc.elapsed=300.;sc.advance(.1,True,[0,0],0)
        public=sc.public();self.assertTrue(public['completed']);self.assertEqual(public['outcome']['phase'],'complete')
        self.assertIn('정차했습니다',public['outcome']['message'])
    def test_rattle_options_use_supported_action(self):
        adapter=NavigationAdapter(SimpleNamespace(scenario=self.trial('rattle')))
        options=adapter.options();self.assertEqual(len(options),4)
        self.assertEqual(next(o for o in options if o['action']=='study_stop_request')['scenario_action'],'stop_request')
    def test_legacy_fog_cannot_be_reused_as_source(self):
        state=dict(profile='fog',scene_id=source_id('fog'),renderer_backend='trained',phase='live')
        self.assertFalse(can_reuse_drive(state,'fog'));state['appearance_mode']='source'
        self.assertTrue(can_reuse_drive(state,'fog'))
    def test_fog_warmup_does_not_publish_or_advance_scenario(self):
        sc=self.trial();b=Bridge.__new__(Bridge);b.scenario=sc;b.jpeg=None;b.frame_id=0
        b.ego=SimpleNamespace(get_transform=lambda:object())
        b.scene=SimpleNamespace(source_timestamp=lambda tr:100,camera_pose=lambda tr:np.eye(4),scene_id='fixture')
        b.render_size=(1280,720);b.intrinsics=object();b.run_dir=Path(sc.events.name).parent
        b.update_tracks=lambda stamp,tr:([],None,sc.public())
        b.stub=Mock();b.stub.render_rgb.with_call.return_value=(SimpleNamespace(image_bytes=b'jpeg-fixture'),object())
        with patch('scene_bridge.proto.RGBRenderRequest',return_value=object()),patch('scene_bridge.validate_jpeg') as check:
            b.warm_fog_compositor();check.assert_called_once()
        self.assertEqual(sc.elapsed,0);self.assertIsNone(b.jpeg);self.assertEqual(b.frame_id,0)
        self.assertIn(('x-nurec-fog','[0.01,11.5]'),b.stub.render_rgb.with_call.call_args.kwargs['metadata'])

if __name__=='__main__':unittest.main()
