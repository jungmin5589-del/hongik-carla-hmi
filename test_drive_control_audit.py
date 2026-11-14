"""Draft controller guards and local projection geometry; not live driving proof."""
import math,threading,unittest
from types import SimpleNamespace as S
import numpy as np
from native_carla_route import HighwayRoute
from native_carla import NativeBridge
class ControlAuditTests(unittest.TestCase):
 def test_local_projection_matches_full_route_across_lap_seam(self):
  pts=[S(transform=S(location=S(x=100*math.cos(t),y=100*math.sin(t),z=0.)),lane_width=3.5) for t in np.linspace(0,2*math.pi,801)]
  r=HighwayRoute(pts)
  for previous in (-5.,0.,5.,100.,r.length-3.,r.length+5.):
   p,_=r.sample(previous+2.);xy=p[:2]+[.2,.1]
   u=np.clip(np.sum((xy-r.points[:-1,:2])*r.delta,axis=1)/r.segment_length**2,0,1)
   distance=np.linalg.norm(r.points[:-1,:2]+r.delta*u[:,None]-xy,axis=1)
   ds=(r.arc[:-1]-previous+r.length/2)%r.length-r.length/2;distance[abs(ds)>80]=np.inf
   i=int(np.argmin(distance));s=float(r.arc[i]+u[i]*r.segment_length[i]);s=previous+(s-previous+r.length/2)%r.length-r.length/2
   projected,error=r.project(xy,previous)
   self.assertAlmostEqual(projected,s,places=7);self.assertAlmostEqual(error,float(distance[i]),places=7)
 def test_damaged_drive_cannot_resume_without_reset(self):
  b=NativeBridge.__new__(NativeBridge);b.lock=threading.RLock();b.state={'drive_guard':'collision','phase':'live'};b.command={'mode':'paused'}
  with self.assertRaisesRegex(ValueError,'다시 준비'):b.control({'mode':'auto'})
  self.assertEqual(b.command['mode'],'paused')
 def test_collision_latches_pause_before_another_request(self):
  b=NativeBridge.__new__(NativeBridge);b.scenario=S(log=lambda *args,**kw:None);b.command={'mode':'auto'};b.state={'phase':'live'};b.profile='congestion'
  e=S(normal_impulse=S(length=lambda:10.),other_actor=S(type_id='vehicle.test',id=1),frame=1)
  b.on_collision(e)
  self.assertEqual(b.command['mode'],'paused');self.assertTrue(b.state['drive_guard']);self.assertEqual(b.scenario.collision_count,1)
