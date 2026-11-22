"""Source-only regression tests. These are not real NuRec render benchmarks."""
import copy,io,json,math,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from PIL import Image
from lab_settings import DEFAULTS
from lab_viewer import preview_layout
from nurec_surround import NuRecSurround,camera_views
from nurec_natural import NaturalBlockade,NaturalWeaving
from nurec_navigation import NuRecNavigation
from nurec_paths import stored_file
from render_options import can_switch,Coordinator
from deploy_nurec_option import deploy,changes,NUREC

def route(length=3000):
    result=np.repeat(np.eye(4)[None],int(length/5)+1,axis=0);result[:,0,3]=np.linspace(0,length,len(result));return result

def fleet():
    large=['22001','22002','22003'];fast=[str(24001+i) for i in range(12)]
    vehicles={'5':dict(size=[4.4,1.9,1.5])};specs=[]
    for key in large+fast:
        size=[10.,2.9,3.8] if key in large else [4.4,1.9,1.5]
        vehicles[key]=dict(size=size,asset_id='/data/already-authorized.ply')
        specs.append(dict(id=key,asset_id='/data/already-authorized.ply',size=size,semantic_class='heavy_truck' if key in large else 'automobile'))
    return dict(lead_track_id='5',large_track_ids=large,fast_track_ids=fast,vehicles=vehicles,insert_assets=specs)

class MotionTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
    def scenario(self,kind):
        obj=kind(route(),Path(self.temp.name)/(kind.__name__+'.jsonl'),fleet()) if kind is NaturalBlockade else kind(route(),Path(self.temp.name)/(kind.__name__+'.jsonl'))
        self.addCleanup(obj.events.close);return obj

    def test_normal_intro_is_straight_and_does_not_start_alert_early(self):
        for kind in (NaturalBlockade,NaturalWeaving):
            sc=self.scenario(kind)
            for _ in range(299):sc.advance(.1,True,[max(0,sc.lead_s-28),0],30)
            self.assertFalse(sc.onset);self.assertGreater(sc.lead_s,200)
            self.assertAlmostEqual(sc.desired_gap,24)
            if kind is NaturalWeaving:self.assertAlmostEqual(sc.pose()[1],0)
            sc.advance(.2,True,[sc.lead_s-28,0],30);self.assertTrue(sc.onset)

    def test_pause_does_not_move_assets_or_advance_intro(self):
        sc=self.scenario(NaturalBlockade);before=copy.deepcopy(sc.traffic_specs())
        sc.advance(1,False,[0,0],0)
        self.assertEqual(sc.elapsed,0);self.assertEqual(before,sc.traffic_specs())

    def test_large_vehicles_stay_separated_and_fast_wrap_is_out_of_view(self):
        sc=self.scenario(NaturalBlockade);self.assertEqual(len(sc.large_ids),6);self.assertEqual(len(sc.fast_ids),24)
        wraps=0
        for _ in range(1400):
            previous=sc.fast_s.copy();ego=max(0,sc.lead_s-12.)
            sc.advance(.1,True,[ego,0],30)
            for before,after in zip(previous,sc.fast_s):
                if after<before:
                    wraps+=1;self.assertGreater(before-ego,200);self.assertLess(after-ego,-60)
                else:self.assertLessEqual(after-before,2.51)
            for i in (1,2,4,5):self.assertGreaterEqual(sc.large_s[i-1]-sc.large_s[i],11.99)
        self.assertGreater(wraps,0)

    def test_heading_tracks_actual_lateral_path_derivative(self):
        sc=self.scenario(NaturalWeaving);sc.onset=True
        # Check the path tangent during onset, normal weaving and horn recovery.
        for horn_at in (None,6.):
            sc.horn_motion_at=horn_at
            for t in (.1,1.,4.,6.,6.5,7.,8.,9.5,10.,13.):
                sc.weave_clock=t;_,_,heading=sc.pose()
                sc.weave_clock=t+.000001;right=sc.pose()[1]
                sc.weave_clock=t-.000001;left=sc.pose()[1]
                self.assertAlmostEqual(math.tan(heading)*sc.weave_reference_speed,(right-left)/.000002,places=5)

    def test_horn_near_source_end_never_spins_or_slides_stopped_scan(self):
        sc=NaturalWeaving(route(312),Path(self.temp.name)/'late-horn.jsonl');self.addCleanup(sc.events.close)
        sc.onset=True;sc.onset_monotonic=0.;sc.dialog_open=True
        sc.elapsed=80.;sc.weave_clock=50.;sc.lead_s=sc.route.length-8.3
        sc.interaction('horn',sc.session)
        previous=sc.pose()[0];maximum_yaw=0.
        for _ in range(160):
            sc.advance(.1,True,[sc.lead_s-12.,0.],0.)
            pose,_,yaw=sc.pose();maximum_yaw=max(maximum_yaw,abs(math.degrees(yaw)))
            self.assertLess(np.linalg.norm(pose[:3,3]-previous[:3,3]),.13)
            previous=pose
        self.assertTrue(sc.completed);self.assertLess(maximum_yaw,20.)
        self.assertEqual(sc.lead_s,sc.route.length-8.)
        stopped=sc.pose()[0].copy()
        sc.advance(.2,False,[sc.lead_s-12.,0.],0.)
        np.testing.assert_array_equal(sc.pose()[0],stopped)

    def test_stationary_horn_does_not_change_vehicle_pose(self):
        sc=self.scenario(NaturalWeaving)
        sc.onset=True;sc.onset_monotonic=0.;sc.dialog_open=True
        sc.elapsed=80.;sc.weave_clock=50.;sc.lead_s=sc.route.length-8.
        before=sc.pose()[0].copy();sc.interaction('horn',sc.session)
        for _ in range(80):sc.advance(.1,True,[sc.lead_s-12.,0.],0.)
        np.testing.assert_array_equal(sc.pose()[0],before)
        self.assertEqual(sc.lead_speed,0.)

    def test_paused_weaving_and_horn_response_are_frozen(self):
        sc=self.scenario(NaturalWeaving)
        sc.onset=True;sc.onset_monotonic=0.;sc.dialog_open=True
        sc.elapsed=40.;sc.weave_clock=10.
        sc.interaction('horn',sc.session);before=sc.pose()[0].copy()
        for _ in range(20):sc.advance(.2,False,[0.,0.],0.)
        np.testing.assert_array_equal(sc.pose()[0],before)
        self.assertEqual(sc.weave_clock,10.)

    def test_short_source_keeps_room_after_the_normal_intro(self):
        sc=NaturalWeaving(route(240),Path(self.temp.name)/'short.jsonl');self.addCleanup(sc.events.close)
        for _ in range(450):sc.advance(.1,True,[max(0,sc.lead_s-12.),0],10.)
        self.assertTrue(sc.onset);self.assertLess(sc.lead_s,sc.route.length-30.)

class ProjectionTests(unittest.TestCase):
    def test_adjacent_panel_edge_rays_match_without_stretch(self):
        cfg=dict(DEFAULTS);views=camera_views(np.eye(4),cfg);edge=math.tan(math.radians(cfg['fov']/2))
        for a,b in (('left','center'),('center','right')):
            ar=views[a][:3,:3]@np.array([edge,0,1]);br=views[b][:3,:3]@np.array([-edge,0,1])
            np.testing.assert_allclose(ar/np.linalg.norm(ar),br/np.linalg.norm(br),atol=1e-12)
        np.testing.assert_allclose(views['center'][:3,3],np.zeros(3))

    def test_external_preview_keeps_all_three_panels(self):
        pos,size,center_only=preview_layout([[0,0,2560,1600],[2560,0,1920,1080]])
        self.assertFalse(center_only);self.assertEqual(size,[1920,360]);self.assertEqual(size[0]/size[1],16/3)

    def render(self,fail=False,cancel=False):
        out=io.BytesIO();Image.new('RGB',(320,180),'#8daccb').save(out,format='JPEG');jpeg=out.getvalue();calls=[]
        class Stub:
            def render_rgb(self,request,timeout):
                calls.append(request)
                if fail and len(calls)==3:raise RuntimeError('third view failed')
                return NS(image_bytes=jpeg)
        proto=NS(CameraSpec=lambda **k:NS(**k),OpenCVPinholeCameraParam=lambda **k:NS(**k),GLOBAL=5,
            RGBRenderRequest=lambda **k:NS(**k),PosePair=lambda **k:NS(**k),ImageFormat=NS(JPEG=2))
        rig=NuRecSurround(dict(DEFAULTS))
        def perform():return rig.render(Stub(),proto,lambda matrix:matrix,'fixture',1234,np.eye(4),['immutable actors'],(320,180),1,lambda:not cancel)
        return rig,calls,perform

    def test_bundle_has_one_timestamp_and_three_real_camera_requests(self):
        rig,calls,perform=self.render();self.assertIsNotNone(perform());self.addCleanup(rig.close)
        self.assertEqual([c.frame_start_us for c in calls],[1234]*3)
        for call in calls:
            self.assertEqual(call.camera_intrinsics.logical_id,'camera_front_wide_120fov')
            self.assertEqual(len(call.camera_intrinsics.opencv_pinhole_param.radial_coeffs),6)
            self.assertEqual(len(call.camera_intrinsics.opencv_pinhole_param.tangential_coeffs),2)
            self.assertEqual(len(call.camera_intrinsics.opencv_pinhole_param.thin_prism_coeffs),4)
        self.assertEqual(len({tuple(c.sensor_pose.start_pose.flatten()) for c in calls}),3)
        with zipfile.ZipFile(io.BytesIO(rig.frames.zip)) as z:self.assertEqual(set(z.namelist()),{'frame.json','left.jpg','center.jpg','right.jpg'})

    def test_failure_or_session_change_never_publishes_partial_bundle(self):
        rig,_,perform=self.render(fail=True)
        with self.assertRaises(RuntimeError):perform()
        self.assertIsNone(rig.frames.zip);rig.close()
        rig,_,perform=self.render(cancel=True);self.assertIsNone(perform());self.assertIsNone(rig.frames.zip);rig.close()

class RequestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.sc=NaturalWeaving(route(),Path(self.temp.name)/'events.jsonl');self.addCleanup(self.sc.events.close)
        self.sc.onset=True;self.sc.elapsed=40.;self.sc.onset_monotonic=0.;self.sc.dialog_open=True
        self.nav=NuRecNavigation(NS(scenario=self.sc));self.nav.last_session=self.sc.session;self.nav.options_open=True;self.nav.choice='study_horn'
    def body(self,action='study_horn',key='one'):
        return dict(action=action,session_id=self.sc.session,navigation_id=self.sc.session+'-weaving',request_id=key,client_event={})

    def test_action_has_cancellable_acknowledgement_before_physical_effect(self):
        first=self.nav.command(self.body());self.assertEqual(self.nav.command(self.body()),first)
        self.assertEqual(self.sc.horn_count,0);self.nav.tick();self.assertEqual(self.sc.horn_count,0)
        self.nav.command(self.body('study_cancel_pending','cancel'));self.sc.elapsed=50;self.nav.tick();self.assertEqual(self.sc.horn_count,0)
        self.nav.command(self.body(key='two'));self.sc.elapsed=70;self.nav.tick();self.assertEqual(self.sc.horn_count,1)
        self.nav.tick();self.assertEqual(self.sc.horn_count,1)

    def test_stale_session_cannot_execute_or_stop(self):
        for action in ('study_horn','study_fixed_stop'):
            body=self.body(action);body['session_id']='previous'
            with self.assertRaises(ValueError):self.nav.command(body)
        self.assertIsNone(self.sc.last_action)

class LaunchTests(unittest.TestCase):
    def test_old_mono_display_is_not_reused_for_surround(self):
        import launch_live
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'launches').mkdir()
            owned={'display':111,'display_layout':'mono'}
            with patch.object(launch_live,'ROOT',root),patch('sys.argv',['launch_live.py','--lab-surround','--no-browser']),patch.object(launch_live.subprocess,'check_output',return_value=('python '+str(root/'live_window.py')).encode()),patch.object(launch_live.subprocess,'run') as stop,patch.object(launch_live.subprocess,'Popen') as start:
                start.return_value.pid=222;launch_live.open_displays(owned)
                self.assertEqual(stop.call_args.args[0],['taskkill','/PID','111','/T','/F'])
                self.assertEqual(Path(start.call_args.args[0][1]).name,'lab_viewer.py')
                self.assertEqual(start.call_args.kwargs['env']['HONGIK_LAB_PREVIEW'],'1')
                self.assertEqual(owned['display_layout'],'surround-preview')

    def test_active_or_paused_unfinished_trials_are_never_killed(self):
        for state in (dict(kind='hongik-nurec',mode='auto'),dict(kind='hongik-native-carla',mode='paused',scenario=dict(elapsed_s=20,completed=False)),dict(kind='unrelated')):
            with self.assertRaises(ValueError):can_switch(state)
        self.assertTrue(can_switch(dict(kind='hongik-nurec',mode='paused',scenario=dict(completed=True))))

    def test_missing_data_is_detected_before_a_worker_can_stop_source(self):
        c=Coordinator()
        with patch('render_options.drive_state',return_value=None),patch('render_options.nurec_preflight',side_effect=FileNotFoundError('SSD missing')),patch('threading.Thread') as worker:
            with self.assertRaisesRegex(FileNotFoundError,'SSD'):c.select(dict(engine='nurec',profile='night'))
            worker.assert_not_called();self.assertEqual(c.status['phase'],'idle')

    def test_old_drive_path_rebases_only_to_existing_licensed_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'source').mkdir();(root/'source/test.usdz').write_bytes(b'fixture')
            self.assertEqual(stored_file('/mnt/d/CARLA-Maps/NuRec-OneScene-20261018/source/test.usdz',root),root/'source/test.usdz')
            with self.assertRaises(FileNotFoundError):stored_file('/mnt/d/CARLA-Maps/NuRec-OneScene-20261018/source/missing.usdz',root)

class DeploymentTests(unittest.TestCase):
    def test_listed_sources_are_available_without_private_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(len(changes(folder,NUREC)),len(NUREC))
            self.assertFalse(any(name.startswith(('vendor/','cache/','source/','mobile-data/')) for name in NUREC))

    def test_dry_run_and_update_preserve_backup_and_private_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'lab_viewer.py').write_text('original')
            (root/'private.pem').write_text('private fixture')
            self.assertEqual(deploy(root,['lab_viewer.py'],dry_run=True),1)
            self.assertEqual((root/'lab_viewer.py').read_text(),'original')
            self.assertEqual(deploy(root,['lab_viewer.py']),1)
            saved=list((root/'backups').glob('*/lab_viewer.py'))
            self.assertEqual(len(saved),1);self.assertEqual(saved[0].read_text(),'original')
            self.assertEqual((root/'private.pem').read_text(),'private fixture')

    def test_destination_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):changes(folder,['../outside.py'])

if __name__=='__main__':unittest.main()
