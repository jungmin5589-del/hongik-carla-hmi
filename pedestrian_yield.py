"""Repeatable pedestrian/vehicle mutual yielding, not gesture recognition."""
import math
import threading
import time

import carla
import numpy as np

from scenario2 import Scenario2
from native_carla_route import HighwayRoute
from city_voice import narration as pedestrian_narration
from pedestrian_gesture import yielding_arm


OPTIONS = [
    dict(action='study_horn', label='클락션', detail='경적을 한 번 울리고 보행자의 반응을 확인합니다.'),
    dict(action='study_highbeam', label='하이빔', detail='상향등을 두 번 점멸하고 보행자의 반응을 확인합니다.'),
    dict(action='study_direct', scenario_action='direct', label='직접 대응',
         detail='승객이 직접 보행자에게 말하고, 대화를 마친 뒤 대응 완료를 누릅니다.'),
    dict(action='study_wait', label='기다리기',
         detail='추가 안내 없이 보행자가 먼저 건널 때까지 기다립니다.')]


class CrossingRoute(HighwayRoute):
    """A bounded real-map route; never wraps or teleports at the end."""
    @classmethod
    def build(cls, road_map):
        polygons, current = [], []
        for p in road_map.get_crosswalks():
            current.append(p)
            if len(current) > 3 and p.distance(current[0]) < .05:
                polygons.append(current[:-1]); current = []
        polygons.sort(key=lambda poly:max(np.ptp([[p.x,p.y] for p in poly],axis=0)))
        routes=[]
        for polygon in polygons:
            centre = np.mean([[p.x,p.y,p.z] for p in polygon], axis=0)
            wp = road_map.get_waypoint(carla.Location(x=float(centre[0]),y=float(centre[1]),z=float(centre[2])))
            # Junction lane links lack adjacent lanes. Choose the curb lane on
            # the outgoing road, then trace back to this marked crossing.
            initial_angle=math.radians(wp.transform.rotation.yaw)
            probe=centre[:2]+15*np.array([math.cos(initial_angle),math.sin(initial_angle)])
            wp=road_map.get_waypoint(carla.Location(x=float(probe[0]),y=float(probe[1]),z=float(centre[2])))
            # Rightmost driving lane keeps the waiting person visible near the curb.
            for _ in range(6):
                adjacent = wp.get_right_lane()
                if not adjacent or adjacent.lane_type != carla.LaneType.Driving or adjacent.lane_id*wp.lane_id <= 0: break
                wp = adjacent
            angle = math.radians(wp.transform.rotation.yaw)
            forward = np.array([math.cos(angle),math.sin(angle)])
            right = np.array([-forward[1],forward[0]])
            poly = np.array([[p.x,p.y] for p in polygon])-centre[:2]
            if np.ptp(poly@right) < 5 or np.ptp(poly@forward) > 6: continue
            back = [wp]; cursor = wp
            for _ in range(42):
                choices = cursor.previous(1.)
                if not choices: break
                cursor = min(choices,key=lambda q:abs((q.transform.rotation.yaw-wp.transform.rotation.yaw+180)%360-180))
                back.append(cursor)
            ahead=[];cursor=wp
            for _ in range(48):
                choices=cursor.next(1.)
                if not choices: break
                cursor=min(choices,key=lambda q:abs((q.transform.rotation.yaw-wp.transform.rotation.yaw+180)%360-180))
                ahead.append(cursor)
            path=list(reversed(back))+ahead
            if len(path)<85 or any(abs((q.transform.rotation.yaw-wp.transform.rotation.yaw+180)%360-180)>6 for q in path): continue
            route=cls(path)
            route.cross_s,_=route.project(centre[:2])
            if route.cross_s<25:continue
            at,_=route.sample(route.cross_s)
            offsets=(np.array([[p.x,p.y] for p in polygon])-at[:2])@right
            if not min(offsets)<-1. or not 1.<max(offsets)<12. or np.ptp(offsets)>20:continue
            route.curb_right=float(max(offsets)+1.0)
            route.curb_left=float(min(offsets)-.25)
            route.lane_offsets=[]
            for lane in road_map.generate_waypoints(3.):
                delta=np.array([lane.transform.location.x,lane.transform.location.y])-at[:2]
                if abs(delta@forward)<2 and abs(delta@right)<18:
                    off=round(float(delta@right),1)
                    if not any(abs(off-x)<1 for x in route.lane_offsets):route.lane_offsets.append(off)
            route.lane_offsets=sorted(route.lane_offsets) or [0.]
            routes.append(route)
        if routes:return min(routes,key=lambda r:(abs(r.curb_right-2.75),r.curb_right-r.curb_left))
        raise RuntimeError('No suitable straight marked crossing was found in Town03.')

    def sample(self,s,offset=0.):
        return super().sample(min(self.length-.001,max(0.,s)),offset)

    def project(self,xy,previous=None):
        return super().project(xy,None)


class YieldScenario(Scenario2):
    TYPE_ID='pedestrian_yield'
    ONSET_SECONDS=0.
    def __init__(self,event_path,route):
        self.lock=threading.RLock();self.enabled=True
        self.events=open(event_path,'a',encoding='utf-8',buffering=1)
        self.cross_s=route.cross_s;self.curb_right=route.curb_right;self.curb_left=route.curb_left
        self.reset()

    def reset(self,enabled=None):
        super().reset(enabled)
        self.phase='approach';self.phase_elapsed=0.;self.wait_elapsed=0.
        self.offset=self.curb_right;self.crossed=False;self.clear_elapsed=0.
        self.support_at=None;self.announcement_count=0;self.signal_until=0.
        self.action_at=None;self.highbeam_at=None;self.direct_pending=False;self.direct_done_at=None
        self.gap=0.;self.last_ego_s=0.;self.result_elapsed=0.

    def interaction(self,action,session):
        if action in ('notification_exposed','open','close'):
            return super().interaction(action,session)
        with self.lock:
            if session!=self.session or not self.onset or not self.dialog_open:
                raise ValueError('현재 보행자 상황 설명을 열어 주세요.')
            if self.phase!='mutual_wait':raise ValueError('보행자가 이미 움직이고 있어요. 현재 대응 결과를 확인해 주세요.')
            self.require_action_available()
            if action not in ('horn','highbeam','direct','maintain'):raise ValueError('지원하지 않는 보행자 대응입니다.')
            self.last_action=action;self.outcome.begin(action)
            self.action_at=self.elapsed
            if action=='horn':
                self.horn_count+=1
                self.feedback='경적을 한 번 울렸습니다. 보행자의 반응을 확인하며 정차합니다.'
            elif action=='highbeam':
                self.highbeam_at=self.elapsed
                self.feedback='상향등을 두 번 점멸합니다. 차량은 정차를 유지합니다.'
            elif action=='direct':
                self.direct_pending=True
                self.feedback='보행자에게 직접 말씀해 주세요. 대화를 마쳤으면 대응 완료를 눌러 주세요.'
            else:self.feedback='현재 양보 판단을 유지하며 보행자가 먼저 건너기를 기다립니다.'
            self.log('action_applied',action=action)
            return self.public()

    def complete_direct(self,session):
        with self.lock:
            if session!=self.session or not self.direct_pending or not self.dialog_open or self.completed:
                raise ValueError('현재 직접 대응 안내를 확인해 주세요.')
            self.direct_pending=False;self.direct_done_at=self.elapsed
            self.feedback='직접 대응을 마쳤습니다. 보행자의 반응을 확인합니다.'
            self.log('passenger_direct_response_completed',source='explicit_button; speech not transcribed')
            return self.public()

    def tick_yield(self,dt,driving,speed,ego_s,actual_offset=None):
        with self.lock:
            self.last_ego_s=ego_s;self.gap=max(0.,self.cross_s-ego_s-2.4)
            if not driving or self.completed:return
            dt=min(.15,max(0.,dt));self.elapsed+=dt;self.phase_elapsed+=dt
            if self.phase=='approach' and self.gap<=9. and speed<.5:
                self.phase='mutual_wait';self.phase_elapsed=0.;self.onset=True
                self.onset_monotonic=time.monotonic();self.log('scenario_onset',stimulus='pedestrian_waves_vehicle_first')
            if self.phase=='mutual_wait':
                self.wait_elapsed+=dt
                signal=self.action_at is not None and self.elapsed-self.action_at>=8. and not self.direct_pending
                # Unclicked and closed dialogs must resolve independently too.
                if signal or (self.wait_elapsed>=75. and not self.direct_pending):
                    self.phase='crossing';self.phase_elapsed=0.
                    self.log('pedestrian_crossing_started',cause=self.last_action if signal else 'automatic')
            elif self.phase=='crossing':
                self.offset=max(self.curb_left,self.offset-1.25*dt) if actual_offset is None else actual_offset
                if self.offset<=self.curb_left+.01:
                    self.phase='clearance';self.phase_elapsed=0.;self.crossed=True
                    self.log('pedestrian_cleared_crosswalk')
            elif self.phase=='clearance' and self.phase_elapsed>=2.:
                self.phase='resume';self.phase_elapsed=0.;self.log('vehicle_resume_authorized')
            elif self.phase=='resume' and ego_s>=self.cross_s+20.:
                self.phase='finishing';self.phase_elapsed=0.
                self.outcome.phase='stopping';self.outcome.status='achieved'
                self.outcome.summary=self.summary();self.log('outcome_observed',summary=self.outcome.summary)
            elif self.phase=='finishing' and speed<.5:
                self.clear_elapsed+=dt
                if self.clear_elapsed>=1.:
                    self.completed=True;self.completion_reason='action_outcome'
                    self.phase='complete';self.outcome.phase='complete';self.feedback=self.summary()
                    self.log('outcome_trial_completed',summary=self.feedback)
            if self.outcome.active and self.outcome.phase=='applying' and self.phase in ('clearance','resume'):
                self.outcome.phase='observing';self.outcome.status='achieved';self.outcome.summary=self.summary()
            if self.outcome.phase=='observing':self.outcome.observed+=dt

    def summary(self):
        prefix={'horn':'경적 후 보행자가 반응해 횡단했습니다. ',
                'highbeam':'상향등 점멸 후 보행자가 반응해 횡단했습니다. ',
                'direct':'승객의 직접 대응 후 보행자가 반응해 횡단했습니다. ',
                'maintain':'추가 안내 없이 기다린 뒤 보행자가 횡단했습니다. '}.get(self.last_action,'별도 선택 없이 기다린 뒤 보행자가 횡단했습니다. ')
        return prefix+'횡단 구간을 벗어난 것을 확인하고 차량이 다시 출발했습니다.'

    def target_speed(self):
        if self.phase=='approach':return min(15.,max(0.,(self.gap-7.5)*1.5))
        if self.phase=='resume':return min(15.,max(0.,(self.cross_s+25.-self.last_ego_s)*1.5))
        return 0.

    def public(self):
        with self.lock:
            return dict(id=self.TYPE_ID,session=self.session,enabled=True,onset=self.onset,
                        elapsed_s=round(self.elapsed,2),duration_s=120,remaining_s=max(0,120-self.elapsed),
                        gap_m=round(self.gap,2),target_gap_m=7.5,horn_count=self.horn_count,
                        high_beam=dict(on=self.highbeam_at is not None and (0<=self.elapsed-self.highbeam_at<.5 or 1.0<=self.elapsed-self.highbeam_at<1.5)),
                        dialog_open=self.dialog_open,action=self.last_action,action_complete=self.crossed,
                        feedback=self.feedback,completed=self.completed,completion_reason=self.completion_reason,
                        outcome=self.outcome.public(),yielding=dict(phase=self.phase,offset_m=self.offset,
                        wait_s=self.wait_elapsed,crossed=self.crossed,announcement_count=self.announcement_count),direct_pending=self.direct_pending,
                        collision_count=getattr(self,'collision_count',0),
                        state_source='Scripted CARLA pedestrian and vehicle; not gesture/intent recognition')


class YieldActor:
    def __init__(self,world,route):
        self.route=route
        bp=world.get_blueprint_library().find('walker.pedestrian.0001')
        if bp.has_attribute('is_invincible'):bp.set_attribute('is_invincible','true')
        if bp.has_attribute('role_name'):bp.set_attribute('role_name','hongik_native_pedestrian')
        xyz,yaw=route.sample(route.cross_s,route.curb_right)
        self.yaw=yaw;self.actor=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=float(xyz[0]),y=float(xyz[1]),z=float(xyz[2]+.3)),carla.Rotation(yaw=math.degrees(yaw)-90)))
        if self.actor is None:raise RuntimeError('Pedestrian curb spawn is blocked.')
        self.pose=None;self.last_phase=None;self.gesture_weight=0.;self.last_elapsed=0.

    def update(self,trial,driving):
        if self.pose is None:self.pose={b.name:b for b in self.actor.get_bones().bone_transforms}
        dt=min(.15,max(0.,trial.elapsed-self.last_elapsed));self.last_elapsed=trial.elapsed
        waving=trial.phase=='mutual_wait'
        self.gesture_weight=min(1.,self.gesture_weight+dt/.7) if waving else max(0.,self.gesture_weight-dt/.7)
        crossing=trial.phase=='crossing' and driving and self.gesture_weight<.001
        entering=trial.phase=='approach' and driving and trial.gap<22. and self.offset()>self.route.curb_right-1.6
        self.actor.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=math.sin(self.yaw),y=-math.cos(self.yaw)),speed=1.25 if crossing else .7 if entering else 0.))
        if self.gesture_weight>0.:
            if waving and self.last_phase!='mutual_wait':
                transform=self.actor.get_transform()
                transform.rotation.yaw=math.degrees(self.yaw)+180.
                self.actor.set_transform(transform)
            self.actor.set_bones(carla.WalkerBoneControlIn(yielding_arm(self.pose,trial.elapsed,self.gesture_weight)))
            self.actor.show_pose()
        else:self.actor.hide_pose()
        self.last_phase=trial.phase

    def cleared(self):
        return self.offset()<=self.route.curb_left+.15

    def offset(self):
        xyz,_=self.route.sample(self.route.cross_s)
        tr=self.actor.get_location();right=np.array([-math.sin(self.yaw),math.cos(self.yaw)])
        return float((np.array([tr.x,tr.y])-xyz[:2])@right)

    def destroy(self):
        try:self.actor.destroy()
        except RuntimeError:pass


def navigation_state(b,options):
    tr=b.ego.get_transform();yaw=math.radians(tr.rotation.yaw);sc=b.scenario.public();r=b.route
    def local(x,y):
        dx,dy=x-tr.location.x,y-tr.location.y
        return dict(forward_m=dx*math.cos(yaw)+dy*math.sin(yaw),right_m=-dx*math.sin(yaw)+dy*math.cos(yaw),up_m=-.4,yaw_deg=0.)
    lanes=[]
    for i,offset in enumerate(r.lane_offsets):
        samples=[]
        for s in np.arange(max(0,b.ego_s-20),min(r.length,b.ego_s+65),2.):
            p,_=r.sample(s,offset);samples.append(dict(**local(p[0],p[1]),width_m=r.width))
        lanes.append(dict(id=i+1,points=samples))
    ped=b.pedestrian.actor;pt=ped.get_transform();pose=local(pt.location.x,pt.location.y)
    actors=[dict(id=ped.id,kind='pedestrian',role='context',label='횡단 대기 보행자',length_m=.5,width_m=.5,height_m=1.75,
                 speed_kmh=ped.get_velocity().length()*3.6,world_pose=dict(x=pt.location.x,y=pt.location.y,yaw=pt.rotation.yaw),**pose)]
    phase=sc['yielding']['phase'];active=phase=='mutual_wait' and not sc['completed']
    descriptions={
        'approach':'횡단보도로 접근하며 보행자의 움직임을 확인하고 있어요.',
        'mutual_wait':pedestrian_narration('city_yield')['text'],
        'crossing':'보행자가 횡단하고 있어요. 횡단 구간을 벗어날 때까지 정차합니다.',
        'clearance':'보행자가 횡단 구간을 벗어났습니다. 주변을 다시 확인하고 있어요.',
        'resume':'횡단 구간이 비어 있는 것을 확인하고 다시 출발합니다.',
        'finishing':'보행자의 반응과 차량의 재출발을 확인했습니다. 차량이 서서히 정차합니다.',
        'complete':sc['feedback']}
    title='보행자와 차량이 서로 양보하며 기다리고 있어요' if phase=='mutual_wait' else descriptions[phase]
    voice=dict(text=descriptions[phase],speaker='Sohee',url=None,cached=False)
    if phase=='mutual_wait':voice=pedestrian_narration('city_yield')
    event=dict(active=active,pending=sc['outcome']['phase']!='idle',outcome=sc['outcome'],feedback=sc['feedback'],
               title=title,description=descriptions[phase],narration=voice,options=options,staged_options=True,
               direct_pending=sc['direct_pending'],hide_eta=True,
               live_detail=f"현재 속도 {b.state['speed_kph']:.0f} km/h · 횡단보도 앞 약 {sc['gap_m']:.1f} m")
    points=r.points[::2,:2].tolist();sid=sc['session']
    return dict(connected=b.state['phase']=='live',schema=2,map='CARLA Town03',renderer='CARLA RGB',
                source='Scripted mutual-yielding trial; not gesture recognition or real remote service',
                frame=b.state['frame'],timestamp=time.time(),actors=actors,road=dict(id=3,lanes=lanes),lane_width_m=r.width,
                ego=dict(id=b.ego.id,**local(tr.location.x,tr.location.y),role='native_carla_ego',speed_kmh=b.state['speed_kph'],
                         lane_index=min(range(len(r.lane_offsets)),key=lambda i:abs(r.lane_offsets[i]))+1,lane_count=len(lanes),lane_id=-1),
                destinations=[],world_pose=dict(x=tr.location.x,y=tr.location.y,yaw=tr.rotation.yaw),
                route=dict(destination=dict(id='yield_end',name='보행자와 서로 양보',point=points[-1],distance_m=round(r.length),detail='신호 없는 횡단보도'),
                           points=points,index=int(b.ego_s/2),remaining_m=max(0,round(r.cross_s+25-b.ego_s)),arrived=False,off_route=False),
                session=dict(session_id=sid,stage='running' if sc['elapsed_s']>0 else 'ready',scenario=4,
                             navigation=dict(id=sid+'-weaving',status='monitoring',map_label='횡단보도 양보',title=title,body=descriptions[phase],research_event=event)),
                nurec=dict(b.state,scenario=sc))
