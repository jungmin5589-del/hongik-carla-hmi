"""Lightweight, scripted window-peering/door-knocking actor; no intent inference."""
import math
import carla
import numpy as np
from pedestrian_gesture import swing_between,carla_rotation
from exterior_dialogue import dialogue_cue,AttentionGate
from exterior_gait import ExteriorGait,stationary_turn

IMPACTS=(.75,1.12,1.72)

def exterior_target(elapsed,start_s,retreat=False,started_at=None,knock_started_at=None):
 if retreat:return 'leaving',start_s+22.,5.8
 if elapsed<4:return 'waiting',start_s+9.,6.4
 if started_at is None:return 'approaching',start_s+2.1,5.35
 if elapsed-started_at<4.3:return 'looking',start_s+2.1,5.35
 if knock_started_at is None:return 'door_approach',start_s+1.35,5.15
 cycle=(elapsed-knock_started_at)%18.
 if cycle<7. or cycle>=13.:return 'knocking',start_s+1.35,5.15
 if cycle<10.:return 'pacing',start_s+1.95,5.3
 return 'pacing',start_s+1.4,5.25

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
  result.append(('crl_Head__C',carla.Transform(b.location,carla.Rotation(pitch=r.pitch+5.,yaw=r.yaw+2.*math.sin(elapsed*.85),roll=r.roll))))
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
  self.attention=AttentionGate()
  self.knock_started_at=None;self.door_speech_at=None
  self.gait=ExteriorGait();self.gaze_error=0.;self.last_gaze_sample=-1.
  self.head_index=self.actor.get_bone_names().index('crl_Head__C')

 def update(self,sc,driving):
  if self.pose is None:self.pose={b.name:b for b in self.actor.get_bones().bone_transforms}
  dt=min(.15,max(0.,sc.elapsed-self.last_elapsed));self.last_elapsed=sc.elapsed
  if not driving:
   self.actor.apply_control(carla.WalkerControl(speed=0.));return
  phase,s,off=exterior_target(sc.elapsed,self.start_s,sc.actor_retreat,self.attention.started_at,self.knock_started_at)
  xyz,yaw=self.route.sample(s,off);tr=self.actor.get_transform()
  dx,dy=float(xyz[0])-tr.location.x,float(xyz[1])-tr.location.y;distance=math.hypot(dx,dy)
  moving=distance>.13 and phase!='waiting' and driving
  pace=1.05 if sc.actor_retreat else .85 if self.attention.started_at is None else .32
  self.actor.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=dx/max(.01,distance),y=dy/max(.01,distance)),speed=pace if moving else 0.))
  speed=self.actor.get_velocity().length()
  look,_=self.route.sample(sc.actual_s+.9,sc.actual_offset)
  look_yaw=math.degrees(math.atan2(float(look[1])-tr.location.y,float(look[0])-tr.location.x))
  facing_error=(look_yaw-tr.rotation.yaw+180.)%360.-180.
  if self.gait.available and sc.elapsed-self.last_gaze_sample>=.09:
   head=self.actor.get_bone_world_transforms()[self.head_index]
   reference=self.gait.idle['comp'][self.gait.names.index('crl_Head__C')]
   forward=np.asarray(head.get_matrix())[:3,:3]@reference.T@np.array([1.,0.,0.])
   gaze_yaw=math.degrees(math.atan2(float(forward[1]),float(forward[0])))
   self.gaze_error=(look_yaw-gaze_yaw+180.)%360.-180.;self.last_gaze_sample=sc.elapsed
  door,_=self.route.sample(sc.actual_s+1.35,sc.actual_offset+1.65)
  door_distance=math.hypot(float(door[0])-tr.location.x,float(door[1])-tr.location.y)
  call,_=self.route.sample(sc.actual_s+2.1,sc.actual_offset+1.85)
  call_distance=math.hypot(float(call[0])-tr.location.x,float(call[1])-tr.location.y)
  # CharacterMovement owns all translating motion. Only turn the body once stopped.
  stationary_turn(self.actor,tr,look_yaw,dt,moving,speed,sc.actor_retreat or phase=='waiting')
  was_started=self.attention.started_at
  started=self.attention.tick(dt,sc.elapsed,call_distance,facing_error,speed,sc.actor_retreat)
  if was_started is None and started is not None:
   sc.log('exterior_dialogue_started',call_distance_m=round(call_distance,3),facing_error_deg=round(facing_error,2),source='actual actor position and orientation')
  near=door_distance<.38 and speed<.15
  door_arrived=near and started is not None and sc.elapsed-started>=4.3 and not sc.actor_retreat
  if door_arrived and self.knock_started_at is None:self.knock_started_at=sc.elapsed
  can_knock=door_arrived and phase in ('door_approach','knocking')
  if can_knock:
   before=knock_count(self.knock_clock);self.knock_clock+=dt;self.knocks+=knock_count(self.knock_clock)-before
   if self.knocks and self.door_speech_at is None:
    self.door_speech_at=sc.elapsed
    sc.log('exterior_door_speech_started',knock_count=self.knocks,window_distance_m=round(door_distance,3),facing_error_deg=round(facing_error,2))
   self.arm_weight=min(1.,self.arm_weight+dt/.55)
  else:self.arm_weight=0.
  if self.gait.available and not sc.actor_retreat:
   bones=dict(self.gait.pose(tr.location,speed,dt,facing_error))
   if can_knock:bones.update((n,t) for n,t in door_pose(self.pose,self.knock_clock,sc.elapsed,self.arm_weight) if n!='crl_Head__C')
   self.actor.set_bones(carla.WalkerBoneControlIn(list(bones.items())));self.actor.show_pose()
  elif not moving and speed<.08 and not sc.actor_retreat:
   self.actor.set_bones(carla.WalkerBoneControlIn(door_pose(self.pose,self.knock_clock,sc.elapsed,self.arm_weight)));self.actor.show_pose()
  else:self.actor.hide_pose()
  cue=dialogue_cue(sc.elapsed,sc.actor_retreat,started,self.door_speech_at)
  self.voice_count=max(self.voice_count,cue['index'])
  origin,road_yaw=self.route.sample(sc.actual_s,sc.actual_offset)
  ax,ay=tr.location.x-float(origin[0]),tr.location.y-float(origin[1])
  sc.exterior=dict(phase=phase,at_window=near,knock_count=self.knocks,knock_clock_s=round(self.knock_clock,3),
                   walk_speed_mps=round(speed,3),local_forward_m=round(ax*math.cos(road_yaw)+ay*math.sin(road_yaw),3),
                   local_right_m=round(-ax*math.sin(road_yaw)+ay*math.cos(road_yaw),3),
                   gait_source='cached_native_cycle_with_mesh_gaze' if self.gait.available else 'native_walk_without_moving_gaze',
                   gaze_error_deg=round(self.gaze_error,2) if self.gait.available else None,gaze_sample_s=self.last_gaze_sample,
                   call_distance_m=round(call_distance,3),knock_started_s=self.knock_started_at,door_speech_started_s=self.door_speech_at,
                   window_distance_m=round(door_distance,3),facing_vehicle=abs(facing_error)<=18.,facing_error_deg=round(facing_error,2),
                   dialogue_started_s=started,dialogue_elapsed_s=round(sc.elapsed-started,3) if started is not None else None,
                   voice_count=self.voice_count,voice_cue=cue,model=self.actor.type_id)

 def cleared(self,ego):return self.actor.get_location().distance(ego.get_location())>9.
 def destroy(self):
  try:self.actor.destroy()
  except RuntimeError:pass
