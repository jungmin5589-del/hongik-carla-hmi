"""Behavioral timing, actions, optical range and camera calibration checks."""
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from fog_trial import DenseFog,fog_at
from fog_effect import FogEffect,transmission
from navigation_adapter import NavigationAdapter


class FogTrialChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        poses=np.repeat(np.eye(4)[None],730,axis=0);poses[:,0,3]=np.arange(730)
        self.sc=DenseFog(poses,Path(self.tmp.name)/'events.jsonl')
    def tearDown(self):self.sc.events.close();self.tmp.cleanup()
    def advance(self,seconds):
        for _ in range(round(seconds*10)):self.sc.advance(.1,True,[0.,0.],0.)
    def test_clear_until_30_seconds_then_continuous_monotonic_fog(self):
        self.assertEqual(fog_at(29.99)['beta'],0.)
        self.assertEqual(fog_at(30.)['beta'],0.)
        self.assertGreater(fog_at(30.1)['beta'],0.)
        values=[fog_at(t)['beta'] for t in np.arange(0,301,.25)]
        self.assertTrue(np.all(np.diff(values)>=0))
        self.assertLess(transmission(15.,fog_at(290)['beta']),.03)
        self.assertLess(transmission(80.,fog_at(60.)['beta']),.2)
    def test_pause_freezes_fog_and_lead_pose(self):
        self.advance(75);before=self.sc.public();pose=self.sc.pose()[0].copy()
        for _ in range(500):self.sc.advance(.1,False,[0,0],0.)
        self.assertEqual(before,self.sc.public());np.testing.assert_array_equal(pose,self.sc.pose()[0])
    def test_no_queue_stops_or_weaving_before_final_braking(self):
        self.assertTrue(np.all(self.sc.speeds[60:2750]>0))
        self.assertTrue(np.all(np.diff(self.sc.positions)>=0))
        self.advance(45)
        self.assertEqual(self.sc.pose()[1:],(0.,0.))
    def test_inspection_does_not_change_driving_policy(self):
        self.advance(31);self.sc.interaction('open',self.sc.session)
        before=(self.sc.lead_s,self.sc.desired_gap,self.sc.target_speed())
        self.sc.interaction('inspect',self.sc.session)
        self.assertEqual(before,(self.sc.lead_s,self.sc.desired_gap,self.sc.target_speed()))
    def test_widen_requires_actual_gap_before_completion(self):
        self.advance(31);self.sc.interaction('open',self.sc.session)
        self.sc.interaction('widen',self.sc.session)
        self.assertFalse(self.sc.action_complete)
        ego=self.sc.lead_s-self.sc.half_length-1.85-self.sc.WIDE_GAP
        self.sc.advance(.1,False,[ego,0.],0.)
        self.assertTrue(self.sc.action_complete)
    def test_stop_request_does_not_fabricate_safe_parking(self):
        self.advance(31);self.sc.interaction('open',self.sc.session)
        self.sc.interaction('stop_request',self.sc.session)
        self.assertTrue(self.sc.stop_requested)
        self.assertFalse(self.sc.public()['safe_stop_verified'])
        self.assertFalse(self.sc.action_complete)
        self.assertIn('확인된 정차 공간이 없어',self.sc.feedback)
    def test_old_session_cannot_act_and_reset_clears_fog(self):
        self.advance(31);old=self.sc.session;self.sc.reset()
        with self.assertRaises(ValueError):self.sc.interaction('widen',old)
        self.assertEqual(self.sc.public()['fog']['beta'],0.)
    def test_nav_explicit_confirmation_and_no_horn_in_fog(self):
        self.advance(31)
        nav=NavigationAdapter(SimpleNamespace(scenario=self.sc,lock=threading.Lock(),command={'mode':'auto'}))
        def body(action,**event):return dict(session_id=self.sc.session,navigation_id=self.sc.session+'-weaving',request_id=uuid.uuid4().hex,action=action,client_event=event)
        with self.assertRaises(ValueError):nav.command(body('study_distance'))
        nav.command(body('study_open'));nav.command(body('study_options'))
        with self.assertRaises(ValueError):nav.command(body('study_choice',choice='study_horn'))
        nav.command(body('study_choice',choice='study_distance'))
        request=body('study_distance');result=nav.command(request)
        self.assertEqual(nav.command(request),result)
        self.assertTrue(self.sc.extra_caution)
        self.assertEqual(self.sc.horn_count,0)


class RangeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.effect=FogEffect()
    def test_near_objects_remain_more_visible_than_far_objects(self):
        a=transmission(np.array([2.,8.,40.,200.]),.08)
        self.assertTrue(np.all(np.diff(a)<0));self.assertGreater(a[0],.8);self.assertLess(a[-1],1e-5)
    def test_spatial_density_field_is_supported(self):
        result=transmission(np.array([[10.,10.]]),np.array([[.1,.2]]))
        self.assertGreater(result[0,0],result[0,1])
    def test_optical_axis_projects_to_calibrated_principal_point(self):
        cam=np.eye(4)
        x,y,r=self.effect.project(np.array([[0.,0.,10.]]),cam)
        cx,cy=self.effect.camera['principal_point'];w,h=self.effect.camera['resolution']
        self.assertLessEqual(abs(x[0]-cx*self.effect.width/w),1.)
        self.assertLessEqual(abs(y[0]-cy*self.effect.height/h),1.)
        self.assertEqual(r[0],10.)
    def test_clear_stage_preserves_original_bytes(self):
        original=b'unmodified-camera-frame'
        result,meta=self.effect.apply(original,None,None,dict(fog=dict(beta=0.)))
        self.assertEqual(original,result);self.assertFalse(meta['applied'])


if __name__=='__main__':unittest.main(verbosity=2)
