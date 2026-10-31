"""Distance-driven native gait replay; visual orientation never overwrites moving actor transforms."""
import json,math
from pathlib import Path
import carla
import numpy as np
from pedestrian_gesture import carla_rotation

CACHE=Path(__file__).resolve().parents[1]/'cache/exterior-gait/walker0034.json'

def rotations_between(a,b,t):
 u,_,vh=np.linalg.svd(a*(1-t)+b*t)
 r=u@vh
 if r.ndim==3:
  bad=np.linalg.det(r)<0;u[bad,:,-1]*=-1
 else:
  if np.linalg.det(r)<0:u[:,-1]*=-1
 return u@vh

def yaw_matrix(degrees):
 a=math.radians(degrees);c,s=math.cos(a),math.sin(a)
 return np.array([[c,-s,0.],[s,c,0.],[0.,0.,1.]])

def gaze_rotations(names,local,component,error):
 """Rotate the visual mesh root, preserving anatomical joints and every translation."""
 result=local.copy()
 if 'crl_root' not in names:return result
 i=names.index('crl_root');parent=component[i]@local[i].T
 result[i]=parent.T@yaw_matrix(error)@parent@local[i]
 return result

def stationary_turn(actor,transform,desired,dt,moving,speed,retreat=False):
 """No transform writes while translating: avoids fighting CharacterMovement."""
 if moving or speed>.08 or retreat:return
 delta=(desired-transform.rotation.yaw+180.)%360.-180.
 if abs(delta)<.2:return
 transform.rotation.yaw+=max(-dt*85.,min(dt*85.,delta));actor.set_transform(transform)

class ExteriorGait:
 def __init__(self):
  self.available=False;self.phase=0.;self.weight=0.;self.previous=None;self.direction=1.
  if not CACHE.is_file():return
  d=json.loads(CACHE.read_text(encoding='utf-8'))
  if d.get('model')!='walker.pedestrian.0034':raise ValueError('Exterior gait model mismatch')
  self.names=d['names'];self.loc=np.asarray([f['loc'] for f in d['frames']]);self.rot=np.asarray([f['rot'] for f in d['frames']]);self.comp=np.asarray([f['comp'] for f in d['frames']])
  self.idle={k:np.asarray(d['idle'][k]) for k in ('loc','rot','comp')}
  self.stride=max(.1,float(d['period_s'])*float(d['reference_speed_mps']))
  if len(self.loc)<8 or not all(np.isfinite(a).all() for a in (self.loc,self.rot,self.comp)):raise ValueError('Invalid exterior gait cache')
  self.available=True

 def pose(self,location,speed,dt,facing_error):
  xy=np.array([location.x,location.y]);distance=0. if self.previous is None else float(np.linalg.norm(xy-self.previous));self.previous=xy
  goal=min(1.,speed/.65);self.weight+=max(-dt*4.,min(dt*4.,goal-self.weight))
  direction=-1. if abs(facing_error)>100 else 1. if abs(facing_error)<80 else self.direction
  self.direction+=max(-dt*5.,min(dt*5.,direction-self.direction))
  if distance<.3:self.phase=(self.phase+self.direction*distance/(self.stride*max(.45,self.weight)))%1.
  at=self.phase*len(self.loc);i=int(at)%len(self.loc);j=(i+1)%len(self.loc);a=at-int(at)
  loc=self.loc[i]*(1-a)+self.loc[j]*a
  rot=rotations_between(self.rot[i],self.rot[j],a);comp=rotations_between(self.comp[i],self.comp[j],a)
  w=self.weight;loc=self.idle['loc']*(1-w)+loc*w
  rot=rotations_between(self.idle['rot'],rot,w);comp=rotations_between(self.idle['comp'],comp,w)
  rot=gaze_rotations(self.names,rot,comp,facing_error)
  return [(n,carla.Transform(carla.Location(x=float(p[0]),y=float(p[1]),z=float(p[2])),carla_rotation(r))) for n,p,r in zip(self.names,loc,rot)]
