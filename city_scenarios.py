"""Carpool exterior disturbance and mechanical-noise experiment conditions."""
import math
import threading
import time

import carla
import numpy as np

from scenario2 import Scenario2
from city_voice import narration
from exterior_actor import ExteriorActor

PROFILES={'carpool':'카풀 대기 중 외부인 접근','rattle':'주행 중 반복되는 이상음'}
OPTIONS={
 'carpool':[
  dict(action='study_relocate',scenario_action='relocate',label='다른 장소로 이동',detail='주변을 확인하고 사람이 물러나면 가까운 대기 장소로 이동합니다.'),
  dict(action='study_external_notice',scenario_action='external_notice',label='외부 스피커로 경고',detail='외부 스피커로 “저는 택시가 아닙니다.”라고 알립니다.'),
  dict(action='study_direct',scenario_action='direct',label='가만히 있는다 (직접 대화)',detail='차량은 정차를 유지합니다. 직접 말씀하신 뒤 대화 완료를 눌러 주세요.'),
  dict(action='study_horn',scenario_action='horn',label='클락션',detail='짧게 경적을 한 번 울리고 상대의 반응을 확인합니다.')],
 'rattle':[
  dict(action='study_inspect',scenario_action='inspect',label='차량 상태 점검 요청하기',detail='현재 차량 상태를 확인하고 추가 점검이 필요한지 살핍니다.'),
  dict(action='study_support',scenario_action='support',label='관제 지원 요청하기',detail='이상음이 발생한 상황을 전달하고 지원 안내를 요청합니다.'),
  dict(action='study_stop_request',scenario_action='safe_stop',label='안전한 장소에 정차 요청하기',detail='비어 있는 갓길을 확인한 경우 이동해 정차합니다.'),
  dict(action='study_wait',scenario_action='maintain',label='현재 주행 유지하기',detail='차량 상태를 살피며 현재 주행을 유지합니다.')]
}


class ContextScenario(Scenario2):
 def __init__(self,profile,event_path,start_s,offset=0.):
  self.profile=profile;self.TYPE_ID='city_'+profile;self.start_s=start_s;self.base_offset=offset
  self.lock=threading.RLock();self.enabled=True
  self.events=open(event_path,'a',encoding='utf-8',buffering=1);self.reset()

 def reset(self,enabled=None):
  super().reset(enabled)
  self.phase='waiting' if self.profile=='carpool' else 'cruising'
  self.action_at=None;self.observe_elapsed=0.;self.stop_elapsed=0.;self.automatic=False
  self.actual_s=self.start_s;self.actual_offset=self.base_offset
  self.actor_retreat=False;self.actor_clear=False;self.shoulder_offset=None;self.safe_location=False
  self.inspection_done=False;self.support_done=False;self.relocation_done=False
  self.announcement_count=0;self.highbeam_on=False;self.sound_started=False
  self.onset_elapsed=None
  self.direct_pending=False;self.direct_done_at=None
  self.exterior=dict(phase='waiting',at_window=False,knock_count=0,knock_clock_s=0.,voice_count=0,model=None)

 def interaction(self,action,session):
  if action in ('notification_exposed','open','close'):
   if action=='close' and self.direct_pending and session==self.session:
    self.direct_pending=False;self.last_action='maintain';self.action_at=self.elapsed
    self.feedback='차량은 정차한 채 주변을 확인하고 있습니다.'
    self.log('passenger_direct_response_cancelled',source='close_button')
   return super().interaction(action,session)
  with self.lock:
   if session!=self.session or not self.onset or not self.dialog_open:raise ValueError('현재 상황 설명을 열어 주세요.')
   self.require_action_available()
   allowed={item['scenario_action'] for item in OPTIONS[self.profile]}
   if action not in allowed:raise ValueError('이 상황의 선택지를 이용해 주세요.')
   self.last_action=action;self.action_at=self.elapsed;self.outcome.begin(action)
   if action=='external_notice':self.announcement_count+=1
   if action=='horn':self.horn_count+=1
   if action=='direct':self.direct_pending=True
   self.feedback={
    'external_notice':'외부 스피커로 “저는 택시가 아닙니다.”라고 알렸습니다. 상대의 반응을 확인합니다.',
    'horn':'짧게 경적을 한 번 울렸습니다. 정차한 채 상대의 반응을 확인합니다.',
    'direct':'차량은 정차를 유지합니다. 직접 말씀하신 뒤 대화 완료를 눌러 주세요.',
    'support':'지원 요청을 접수했습니다. 차량 상태를 확인하며 속도를 낮춥니다.',
    'relocate':'주변을 확인하고 같은 주차 구역 안에서 대기 위치를 변경합니다.',
    'inspect':'차량 상태를 확인하고 있습니다. 소리만으로 원인을 단정하지 않고 주변을 살핍니다.',
    'safe_stop':'비어 있는 갓길을 확인하며 감속하고 있습니다.',
    'maintain':'현재 대응을 유지하며 주변과 차량 상태를 확인합니다.'}[action]
   self.log('action_applied',action=action,profile=self.profile)
   return self.public()

 def complete_direct(self,session):
  with self.lock:
   if session!=self.session or not self.direct_pending or not self.dialog_open or self.completed:
    raise ValueError('현재 직접 대화 안내를 확인해 주세요.')
   self.direct_pending=False;self.direct_done_at=self.elapsed;self.action_at=self.elapsed
   self.feedback='대화를 마쳤습니다. 정차한 채 상대의 반응을 확인합니다.'
   self.log('passenger_direct_response_completed',source='explicit_button; speech not transcribed')
   return self.public()

 def tick_context(self,dt,driving,speed,s,offset,actor_clear=False,safe_location=False):
  with self.lock:
   self.actual_s=s;self.actual_offset=offset;self.actor_clear=actor_clear;self.safe_location=safe_location
   if not driving or self.completed:return
   dt=min(.15,max(0.,dt));self.elapsed+=dt
   start=self.exterior.get('dialogue_started_s')
   ready=(start is not None and self.elapsed>=start+.2) if self.profile=='carpool' else self.elapsed>=8.
   if not self.onset and ready:
    self.onset=True;self.onset_monotonic=time.monotonic();self.phase='event'
    self.onset_elapsed=self.elapsed
    self.log('scenario_onset',profile=self.profile,stimulus='scripted audio and actor state')
   if not self.onset:return
   if self.action_at is None and self.elapsed>=self.onset_elapsed+75.:
    self.automatic=True;self.action_at=self.elapsed;self.outcome.begin('automatic')
   if self.action_at is None:return
   if self.direct_pending:return
   age=self.elapsed-self.action_at
   self.support_done=self.last_action=='support' and age>=8.
   self.inspection_done=self.last_action=='inspect' and age>=8.
   if self.profile=='carpool':
    self.actor_retreat=age>=6. or self.last_action=='relocate'
    self.relocation_done=self.last_action=='relocate' and s>=self.start_s+5.5 and speed<.5
    ready=actor_clear and (self.last_action!='relocate' or self.relocation_done)
   else:
    ready=safe_location and speed<.5 if self.last_action=='safe_stop' and self.shoulder_offset is not None else age>=8.
    if self.last_action=='safe_stop' and self.shoulder_offset is None:ready=speed<.5 and age>=8.
   if self.outcome.phase=='applying' and age>=8. and ready:
    self.phase='result';self.action_complete=True
    self.outcome.phase='observing';self.outcome.status='partial' if self.last_action=='safe_stop' and self.shoulder_offset is None else 'achieved'
    self.outcome.summary=self.summary();self.feedback=self.outcome.summary
    self.log('outcome_observation_started',action=self.last_action,status=self.outcome.status)
   elif self.outcome.phase=='observing':
    self.observe_elapsed+=dt;self.outcome.observed=self.observe_elapsed
    if self.observe_elapsed>=12.:self.phase='finishing';self.outcome.phase='stopping';self.log('outcome_observed',action=self.last_action)
   elif self.outcome.phase=='stopping':
    self.stop_elapsed=self.stop_elapsed+dt if speed<.5 else 0.
    if self.stop_elapsed>=1.:
     self.completed=True;self.phase='complete';self.completion_reason='action_outcome';self.outcome.phase='complete'
     self.feedback=self.summary();self.log('outcome_trial_completed',action=self.last_action)

 def target(self):
  if self.phase in ('finishing','complete'):return 0.,self.actual_offset
  age=0. if self.action_at is None else self.elapsed-self.action_at
  if self.profile=='carpool':
   if self.last_action=='relocate':return (max(0.,min(5.,(self.start_s+6.-self.actual_s)*2)) if self.actor_clear else 0.),self.base_offset
   return 0.,self.base_offset
  if self.last_action=='safe_stop':
   if self.shoulder_offset is None:return 0.,0.
   u=min(1.,max(0.,age/8.));u=u*u*(3-2*u)
   if self.safe_location and abs(self.actual_offset-self.shoulder_offset)<.55:return 0.,self.shoulder_offset
   return 7.,self.shoulder_offset*u
  return (12. if self.last_action=='support' else 18.),0.

 def summary(self):
  if self.profile=='carpool':
   return {
    'external_notice':'외부 안내 후 사람이 차량에서 물러나는 반응을 확인했습니다. 문이 닫힌 상태로 대기를 유지했습니다.',
    'horn':'경적을 울린 뒤 사람이 차량에서 물러났습니다. 정차 상태로 주변을 확인하고 있습니다.',
    'direct':'직접 대화를 마친 뒤 사람이 차량에서 물러났습니다. 차량은 정차를 유지하고 있습니다.',
    'relocate':'같은 주차 구역의 다른 위치로 이동해 정차했습니다. 외부인과의 거리가 늘어난 것을 확인했습니다.',
    'maintain':'추가 안내 없이 대기를 유지했습니다. 외부인이 물러난 뒤에도 주변을 확인했습니다.'}.get(self.last_action,'별도 요청 없이 대기를 유지했고 외부인이 물러나는 상황을 확인했습니다.')
  return {
   'inspect':'현재 정보만으로 이상음의 원인을 확정하지 못했습니다. 차량 상태를 살피고 있습니다.',
   'support':'이상음에 대한 지원 요청을 접수했습니다. 속도를 낮추고 차량 상태를 확인하고 있습니다.',
   'safe_stop':'비어 있는 갓길로 이동해 정차했습니다. 이상음 상황에서 정차한 결과를 확인했습니다.' if self.shoulder_offset is not None else '안전한 정차 공간을 확인하지 못해 감속 후 현재 위치에서 주행을 중지했습니다. 갓길 정차 완료가 아닙니다.',
   'maintain':'추가 요청 없이 주행을 유지했습니다. 이상음이 이어지는 동안 차량 상태를 확인했습니다.'}.get(self.last_action,'차량 상태를 확인한 뒤 정차했습니다.')

 def public(self):
  with self.lock:
   return dict(id=self.TYPE_ID,session=self.session,enabled=True,onset=self.onset,elapsed_s=round(self.elapsed,2),
               duration_s=180,remaining_s=max(0,180-self.elapsed),gap_m=0,target_gap_m=0,horn_count=self.horn_count,high_beam=dict(on=False),
               dialog_open=self.dialog_open,action=self.last_action,action_complete=self.action_complete,feedback=self.feedback,
               completed=self.completed,completion_reason=self.completion_reason,outcome=self.outcome.public(),direct_pending=self.direct_pending,
               context=dict(profile=self.profile,phase=self.phase,actor_retreat=self.actor_retreat,actor_clear=self.actor_clear,
                            door_closed=True,inspection_done=self.inspection_done,support_done=self.support_done,
                            relocation_done=self.relocation_done,announcement_count=self.announcement_count,
                            safe_location=self.safe_location,shoulder_available=self.shoulder_offset is not None,
                            outside_voice_count=self.exterior['voice_count'] if self.profile=='carpool' else 0,
                            exterior=self.exterior.copy() if self.profile=='carpool' else None,
                            rattle_active=self.profile=='rattle' and self.onset and not self.completed,
                            sound_kind='loose_underbody_cover' if self.profile=='rattle' else None),
               collision_count=getattr(self,'collision_count',0),
               state_source='scripted CARLA actors and synthesized sound; not intoxication or mechanical fault detection')


def find_shoulder(route,road_map,s):
 for off in (9.8,10.2,10.6,11.):
  good=True
  for d in (-1.1,0.,1.1):
   p,_=route.sample(s,off+d)
   wp=road_map.get_waypoint(carla.Location(x=float(p[0]),y=float(p[1]),z=float(p[2])),project_to_road=False,lane_type=carla.LaneType.Any)
   if not wp or wp.lane_type not in (carla.LaneType.Shoulder,carla.LaneType.Parking):good=False;break
  if good:return off
 return None


def navigation_state(b,options):
 sc=b.scenario.public();tr=b.ego.get_transform();yaw=math.radians(tr.rotation.yaw);route=b.route
 def local(x,y):
  dx,dy=x-tr.location.x,y-tr.location.y
  return dict(forward_m=dx*math.cos(yaw)+dy*math.sin(yaw),right_m=-dx*math.sin(yaw)+dy*math.cos(yaw),up_m=-.4,yaw_deg=0.)
 offsets=route.lane_offsets if b.profile=='carpool' else [(i-1)*route.width for i in range(4)]
 lanes=[]
 for i,off in enumerate(offsets):
  samples=[]
  for d in range(-20,81,3):
   p,_=route.sample(b.ego_s+d,off);samples.append(dict(**local(p[0],p[1]),width_m=route.width))
  lanes.append(dict(id=i+1,points=samples))
 actors=[]
 if b.pedestrian:
  p=b.pedestrian.actor.get_transform()
  actors.append(dict(id=b.pedestrian.actor.id,kind='pedestrian',role='context',label='차량 주변 사람',length_m=.5,width_m=.5,height_m=1.8,
                     speed_kmh=b.pedestrian.actor.get_velocity().length()*3.6,world_pose=dict(x=p.location.x,y=p.location.y,yaw=p.rotation.yaw),**local(p.location.x,p.location.y)))
 voice=narration('city_'+b.profile);title='차량 밖의 소리와 사람의 접근을 확인하고 있어요' if b.profile=='carpool' else '차량 하부에서 반복적인 소리가 들리고 있어요'
 if not sc['onset']:title='동승자를 기다리고 있어요' if b.profile=='carpool' else '차량 상태를 살피며 주행합니다'
 if sc['outcome']['phase']!='idle':title='차량이 정차했습니다' if sc['completed'] else '요청한 대응을 진행하고 있어요'
 event=dict(active=sc['onset'] and sc['outcome']['phase']=='idle' and not sc['completed'],pending=sc['outcome']['phase']!='idle',
            outcome=sc['outcome'],title=title,description=voice['text'] if sc['outcome']['phase']=='idle' else sc['feedback'],
            narration=voice,feedback=sc['feedback'],options=options,staged_options=True,hide_eta=True,
            direct_pending=sc['direct_pending'],direct_label='대화 완료' if b.profile=='carpool' else '대응 완료',
            live_detail=({'waiting':'동승자 대기 중','approaching':'차량 쪽으로 접근 중','looking':'차량 안쪽을 바라보는 중','door_approach':'조수석 문 쪽으로 이동 중','peering':'차량 안쪽을 들여다보는 중','knocking':'조수석 문 가까이에서 움직이는 중','pacing':'차량 옆을 오가는 중','leaving':'차량에서 물러나는 중'}.get(sc['context']['exterior']['phase'],'주변 확인 중')+' · 문 닫힘 유지') if b.profile=='carpool' else f"현재 속도 {b.state['speed_kph']:.0f} km/h")
 points=route.points[::3,:2].tolist();sid=sc['session'];map_name='CARLA Town03' if b.profile=='carpool' else 'CARLA Town04'
 return dict(connected=b.state['phase']=='live',schema=2,renderer='CARLA RGB',map=map_name,frame=b.state['frame'],timestamp=time.time(),
             source='Scripted passenger interaction and audio, not automated diagnosis',road=dict(id=30,lanes=lanes),lane_width_m=route.width,actors=actors,destinations=[],
             ego=dict(id=b.ego.id,role='native_carla_ego',**local(tr.location.x,tr.location.y),speed_kmh=b.state['speed_kph'],lane_index=2,lane_count=len(lanes),lane_id=-2),
             world_pose=dict(x=tr.location.x,y=tr.location.y,yaw=tr.rotation.yaw),
             route=dict(destination=dict(id='city_end',name='동승자 대기 장소' if b.profile=='carpool' else '목적지',point=points[-1],distance_m=0,detail='정차 중' if b.profile=='carpool' else '주행 중'),points=points,index=0,remaining_m=0,arrived=False,off_route=False),
             session=dict(session_id=sid,stage='running' if sc['elapsed_s']>0 else 'ready',scenario=5 if b.profile=='carpool' else 6,
                          navigation=dict(id=sid+'-weaving',status='monitoring',map_label=PROFILES[b.profile],title=title,body=event['description'],research_event=event)),
             nurec=dict(b.state,scenario=sc))
