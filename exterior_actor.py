"""Lightweight, scripted window-peering/door-knocking actor; no intent inference."""
import math
import carla
import numpy as np
from pedestrian_gesture import swing_between,carla_rotation
from exterior_dialogue import dialogue_cue

IMPACTS=(.75,1.12,1.72)

def exterior_target(elapsed,start_s,retreat=False):
 if retreat:return 'leaving',start_s+22.,5.8
 if elapsed<4:return 'waiting',start_s+12.,7.
 if elapsed<11:return 'approaching',start_s+4.,5.9
 cycle=(elapsed-11.)%22.
 if cycle<5:return 'peering',start_s+2.6,5.45
 if cycle<15:return 'knocking',start_s+1.35,5.15
 return 'pacing',start_s+4.,5.85

def knock_count(clock):
 clock=max(0.,clock)
 return int(clock//5.)*len(IMPACTS)+sum(clock%5.>=t for t in IMPACTS)

def door_pose(rest,clock,elapsed,weight=1.):
 """Two joint rotations, original bone translations/wrists, restrained torso lean."""
 upper,fore,hand=(rest[n] for n in ('crl_arm__R','crl_foreArm__R','crl_hand__R'))
 parent=np.asarray(rest['crl_shoulder__R'].component.get_matrix())[:3,:3]
 um,fm,hm=(np.asarray(b.component.get_matrix()) for b in (upper,fore,hand))
 upper_vector=fm[:3,3]-um[:3,3];fore_vector=hm[:3,3]-fm[:3,3]
 phase=clock%5.;hit=max(math.exp(-((phase-t)/.10)**2) for t in IMPACTS)
 lift=swing_between(upper_vector,[.16,.10,-.16],weight)
 ur=lift@um[:3,:3]
 bend=swing_between(lift@fore_vector,[.23+.13*hit,-.025,.15],weight)
 fr=bend@lift@fm[:3,:3]
 result=[('crl_arm__R',carla.Transform(upper.relative.location,carla_rotation(parent.T@ur))),
         ('crl_foreArm__R',carla.Transform(fore.relative.location,carla_rotation(ur.T@fr)))]
 # Head search motion is small; no wrist/finger deformation or skeleton scaling.
 if 'crl_Head__C' in rest:
  b=rest['crl_Head__C'].relative;r=b.rotation
  result.append(('crl_Head__C',carla.Transform(b.location,carla.Rotation(pitch=r.pitch+5.,yaw=r.yaw+10.*math.sin(elapsed*.85),roll=r.roll))))
 return result

class ExteriorActor:
 def __init__(self,world,route,start_s):
  self.route,self.start_s=route,start_s
  library=world.get_blueprint_library()
  # Reviewed built-in loose dark burgundy top, dark trousers; appearance is not a diagnosis.
  bp=library.find('walker.pedestrian.0034')
  if bp.has_attribute('is_invincible'):bp.set_attribute('is_invincible','true')
  if bp.has_attribute('role_name'):bp.set_attribute('role_name','hongik_native_exterior')
  p,a=route.sample(start_s+9.,6.4)
  self.actor=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=float(p[0]),y=float(p[1]),z=float(p[2]+.4)),carla.Rotation(yaw=math.degrees(a)+180)))
  if self.actor is None:raise RuntimeError('Exterior person spawn is blocked')
  self.pose=None;self.last_elapsed=0.;self.knock_clock=0.;self.knocks=0;self.voice_count=0;self.arm_weight=0.

 def update(self,sc,driving):
  if self.pose is None:self.pose={b.name:b for b in self.actor.get_bones().bone_transforms}
  dt=min(.15,max(0.,sc.elapsed-self.last_elapsed));self.last_elapsed=sc.elapsed
  if not driving:
   self.actor.apply_control(carla.WalkerControl(speed=0.));return
  phase,s,off=exterior_target(sc.elapsed,self.start_s,sc.actor_retreat)
  xyz,yaw=self.route.sample(s,off);tr=self.actor.get_transform()
  dx,dy=float(xyz[0])-tr.location.x,float(xyz[1])-tr.location.y;distance=math.hypot(dx,dy)
  moving=distance>.22 and phase!='waiting' and driving
  self.actor.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=dx/max(.01,distance),y=dy/max(.01,distance)),speed=(1.05 if sc.actor_retreat else .9) if moving else 0.))
  near=distance<.38 and phase in ('peering','knocking')
  if near and driving:
   desired=math.degrees(yaw)-90.+(7.*math.sin(sc.elapsed*1.1) if phase=='peering' else 0.)
   delta=(desired-tr.rotation.yaw+180.)%360.-180.
   tr.rotation.yaw+=max(-dt*100.,min(dt*100.,delta));self.actor.set_transform(tr)
  if near and phase=='knocking' and driving:
   before=knock_count(self.knock_clock);self.knock_clock+=dt;self.knocks+=knock_count(self.knock_clock)-before
   self.arm_weight=min(1.,self.arm_weight+dt/.55)
   self.actor.set_bones(carla.WalkerBoneControlIn(door_pose(self.pose,self.knock_clock,sc.elapsed,self.arm_weight)));self.actor.show_pose()
  elif near and phase=='peering':
   self.arm_weight=0.;b=self.pose['crl_Head__C'].relative;r=b.rotation
   self.actor.set_bones(carla.WalkerBoneControlIn([('crl_Head__C',carla.Transform(b.location,carla.Rotation(pitch=r.pitch+7.,yaw=r.yaw+16.*math.sin(sc.elapsed*.85),roll=r.roll)))]));self.actor.show_pose()
  else:self.arm_weight=0.;self.actor.hide_pose()
  cue=dialogue_cue(sc.elapsed,sc.actor_retreat)
  self.voice_count=max(self.voice_count,cue['index'])
  sc.exterior=dict(phase=phase,at_window=near,knock_count=self.knocks,knock_clock_s=round(self.knock_clock,3),
                   voice_count=self.voice_count,voice_cue=cue,model=self.actor.type_id)

 def cleared(self,ego):return self.actor.get_location().distance(ego.get_location())>9.
 def destroy(self):
  try:self.actor.destroy()
  except RuntimeError:pass
