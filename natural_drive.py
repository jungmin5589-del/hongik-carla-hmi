"""Source-faithful fog/sound trials: no moved or inserted close-up lead asset.

Physical ego follows the recorded corridor. Original actors retain source poses.
No claim of a verified pull-over bay or new reconstructed geometry.
"""
import math
import threading
import time
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from scenario2 import Scenario2
from fog_trial import fog_at
from city_voice import narration


class RecordedTraffic:
    def __init__(self,data,alignment):
        self.rows=[];self.alignment=alignment
        for key,label,poses,stamps in zip(data['tracks_id'],data['tracks_label_class'],data['tracks_poses'],data['tracks_timestamps_us']):
            poses=np.asarray(poses,dtype=float);ts=np.asarray(stamps,dtype=np.int64)
            if len(ts)<2 or label not in ('automobile','heavy_truck','bus','trailer','person','rider'):continue
            unique=np.r_[True,np.diff(ts)>0];ts=ts[unique];poses=poses[unique]
            if len(ts)<2:continue
            self.rows.append(dict(id=str(key),label=label,poses=poses,ts=ts,slerp=Slerp(ts-ts[0],Rotation.from_quat(poses[:,3:]))))

    def sample(self,stamp):
        result={}
        for row in self.rows:
            ts=row['ts']
            if not ts[0]<=stamp<=ts[-1]:continue
            k=min(len(ts)-2,max(0,int(np.searchsorted(ts,stamp))-1));u=(stamp-ts[k])/(ts[k+1]-ts[k])
            matrix=np.eye(4);matrix[:3,3]=(1-u)*row['poses'][k,:3]+u*row['poses'][k+1,:3]
            matrix[:3,:3]=row['slerp'](stamp-ts[0]).as_matrix()
            result[row['id']]=matrix
        return result

    def proxy_ids(self,rig_poses,rig_stamps,limit=10):
        # Keep source vehicles that come closest to the observed driving corridor.
        scores=[]
        for row in self.rows:
            ts=row['ts'];points=row['poses'][:,:3]
            rig=np.column_stack([np.interp(ts,rig_stamps,rig_poses[:,i,3]) for i in range(3)])
            distance=np.linalg.norm(points-rig,axis=1)
            scores.append((float(distance.min()),row['id']))
        return {key for _,key in sorted(scores)[:limit]}


class RecordedCamera:
    def __init__(self,poses,stamps):
        self.poses=np.asarray(poses);self.stamps=np.asarray(stamps);self.rotations=Slerp(self.stamps-self.stamps[0],Rotation.from_matrix(self.poses[:,:3,:3]))
    def sample(self,stamp):
        stamp=float(np.clip(stamp,self.stamps[0],self.stamps[-1]));k=min(len(self.stamps)-2,max(0,int(np.searchsorted(self.stamps,stamp))-1))
        u=(stamp-self.stamps[k])/(self.stamps[k+1]-self.stamps[k]);pose=np.eye(4)
        pose[:3,3]=(1-u)*self.poses[k,:3,3]+u*self.poses[k+1,:3,3];pose[:3,:3]=self.rotations(stamp-self.stamps[0]).as_matrix();return pose
    def stabilize(self,actual,stamp):
        source=self.sample(stamp);distance=float(np.linalg.norm(actual[:2,3]-source[:2,3]))
        angle=float(Rotation.from_matrix(source[:3,:3].T@actual[:3,:3]).magnitude())
        # Do not hide significant off-route motion or a large rotation.
        weight=min(max(0.,min(1.,(distance-.25)/.4)),1.)
        weight=max(weight,max(0.,min(1.,(angle-math.radians(3))/math.radians(9))))
        weight=weight*weight*(3-2*weight)
        pose=np.eye(4);pose[:3,3]=(1-weight)*source[:3,3]+weight*actual[:3,3]
        pose[:3,:3]=Slerp([0,1],Rotation.from_matrix(np.stack([source[:3,:3],actual[:3,:3]])))(weight).as_matrix()
        return pose,dict(mode='recorded-rig bounded stabilization',physical_weight=weight,lateral_error_m=distance,angle_error_deg=math.degrees(angle))


class NaturalDrive(Scenario2):
    SOURCE_FAITHFUL=True
    SUPPRESS_OTHER_TRAFFIC=False
    TRACK_ID='source_traffic'
    ONSET_SECONDS=8.
    TYPE_ID='city_rattle'

    def __init__(self,profile,route,event_path,proxy_ids):
        self.profile=profile;self.TYPE_ID='dense_fog' if profile=='fog' else 'city_rattle'
        self.ONSET_SECONDS=10. if profile=='fog' else 8.;self.source_proxy_ids=set(proxy_ids)
        super().__init__(route,event_path)
    def reset(self,enabled=None):
        super().reset(enabled)
        self.duration=300.;self.action_at=None;self.observed=0.;self.stop_elapsed=0.;self.caution=False
        self.actual_speed=0.;self.nearest_gap=None;self.gap=999.;self.desired_gap=8.;self.safe_stop_verified=False
        self.cruise=min(24.,max(5.,(self.route.length-15.)/285.*3.6));self.feedback=''
    def advance(self,dt,driving,ego_xy,speed):
        with self.lock:
            self.ego_s=self.route.project(ego_xy);self.actual_speed=speed
            if not driving or self.completed:return self.target_speed()
            dt=min(.2,max(0.,dt));self.elapsed+=dt
            if not self.onset and self.elapsed>=self.ONSET_SECONDS:
                self.onset=True;self.onset_monotonic=time.monotonic();self.log('scenario_onset',profile=self.profile)
            if self.outcome.active:
                age=self.elapsed-self.action_at
                if self.outcome.phase=='applying' and age>=8.:
                    if self.last_action!='stop_request' or speed<=self.cruise*.65+1.:
                        self.outcome.phase='observing';self.outcome.status='partial' if self.last_action=='stop_request' else 'achieved'
                        self.outcome.summary=self.describe();self.feedback=self.outcome.summary
                elif self.outcome.phase=='observing':
                    self.observed+=dt;self.outcome.observed=self.observed
                    if self.observed>=12.:self.outcome.phase='stopping'
                elif self.outcome.phase=='stopping':
                    self.stop_elapsed=self.stop_elapsed+dt if speed<.5 else 0.
                    if self.stop_elapsed>=1.:
                        self.completed=True;self.completion_reason='action_outcome';self.outcome.phase='complete';self.action_complete=True
                        self.outcome.summary=self.describe();self.feedback=self.outcome.summary
            elif self.elapsed>=300. and speed<.5:
                self.completed=True;self.completion_reason='duration_end';self.feedback='차량이 정차했습니다.'
                self.outcome.phase='complete';self.outcome.status='achieved';self.outcome.summary=self.feedback
            return self.target_speed()
    def target_speed(self):
        if self.completed or self.outcome.phase in ('stopping','complete') or self.elapsed>=300:return 0.
        start=min(1.,self.elapsed/6.);end=min(1.,max(0.,(300-self.elapsed)/16.))
        factor=.65 if self.caution else 1.
        target=self.cruise*start*start*(3-2*start)*end*end*(3-2*end)*factor
        if self.nearest_gap is not None:target=min(target,max(0.,(self.nearest_gap-8)*1.8))
        return target
    def pose(self):return None,0.,0.
    def interaction(self,action,session):
        if action in ('notification_exposed','open','close'):return super().interaction(action,session)
        with self.lock:
            if session!=self.session or not self.onset or not self.dialog_open:raise ValueError('현재 상황을 먼저 확인해 주세요.')
            self.require_action_available()
            allowed={'inspect','widen','stop_request'} if self.profile=='fog' else {'inspect','support','stop_request','maintain'}
            if action not in allowed:raise ValueError('현재 상황의 대응을 선택해 주세요.')
            self.last_action=action;self.action_at=self.elapsed;self.caution=action in ('widen','stop_request','support')
            self.outcome.begin(action);self.feedback=self.describe();self.log('action_applied',action=action,verified_pull_over=False)
            return self.public()
    def describe(self):
        if self.last_action=='stop_request':return '확인된 정차 공간이 없어 경로를 벗어나지 않고 감속했습니다. 안전한 장소로 이동해 정차한 상태는 아닙니다.'
        if self.last_action=='widen':return '속도를 더 낮추고 전방 교통과 시야를 확인하고 있습니다.'
        if self.last_action=='support':return '지원 요청을 접수했습니다. 속도를 낮추고 차량 상태를 확인하고 있습니다.'
        if self.last_action=='inspect':return '현재 속도와 주변 상황을 확인했습니다. 이상음의 원인은 아직 확인되지 않았습니다.' if self.profile=='rattle' else '감속 상태와 전방 시야를 확인했습니다. 짙은 안개 속에서 주행하고 있습니다.'
        return '차량 상태와 주변을 살피며 현재 경로를 유지하고 있습니다.'
    def public(self):
        with self.lock:
            outcome=self.outcome.public()
            if self.completed and self.completion_reason=='duration_end':outcome['message']='차량이 정차했습니다. 주변 상황을 확인하고 있습니다.'
            elif outcome['phase']=='complete' and outcome['status']=='partial':outcome['message']='정차 요청은 부분적으로 반영되었습니다. 안전한 정차 공간은 확인되지 않았습니다.'
            result=dict(id=self.TYPE_ID,session=self.session,enabled=self.enabled,onset=self.onset,elapsed_s=round(self.elapsed,3),
                duration_s=300,remaining_s=max(0,300-self.elapsed),gap_m=self.nearest_gap,target_gap_m=None,horn_count=0,high_beam={'on':False},
                dialog_open=self.dialog_open,action=self.last_action,action_complete=self.action_complete,feedback=self.feedback,
                completed=self.completed,completion_reason=self.completion_reason,outcome=outcome,source_faithful=True,
                safe_stop_verified=False,state_source='Original source traffic, physical CARLA ego, scripted fog/sound stimulus')
            if self.profile=='fog':result.update(fog=fog_at(self.elapsed))
            else:result['context']=dict(profile='rattle',phase='complete' if self.completed else 'event' if self.onset else 'cruising',
                exterior=None,rattle_active=self.onset and not self.completed,sound_kind='loose_underbody_cover',announcement_count=0)
            return result


def navigation_state(bridge,options):
    sc=bridge.scenario.public();tr=bridge.ego.get_transform();yaw=math.radians(tr.rotation.yaw)
    def local(x,y,angle=0):
        dx,dy=x-tr.location.x,y-tr.location.y
        return dict(forward_m=dx*math.cos(yaw)+dy*math.sin(yaw),right_m=-dx*math.sin(yaw)+dy*math.cos(yaw),up_m=-.4,yaw_deg=(angle-tr.rotation.yaw+180)%360-180)
    actors=[]
    for row in getattr(bridge,'source_actor_state',[]):
        pose=row['aligned'];x,y=pose[0,3],-pose[1,3];p=local(x,y,-math.degrees(math.atan2(pose[1,0],pose[0,0])))
        if not -45<p['forward_m']<180 or abs(p['right_m'])>25:continue
        dims=getattr(bridge,'track_dimensions',{}).get(row['id'],[4.5,1.8,1.6])
        actors.append(dict(id=row['id'],role='context',kind='vehicle',label='주변 차량',length_m=dims[0],width_m=dims[1],height_m=dims[2],
            vehicle_type='large' if dims[0]>6 else 'car',world_pose=dict(x=x,y=y,yaw=0),**p))
    lanes=[];route=bridge.scenario.route
    for i,off in enumerate((0.,-3.6)):
        samples=[]
        for d in range(-25,140,5):
            pose=route.sample(bridge.scenario.ego_s+d,lateral=off,height=0);p=local(pose[0,3],-pose[1,3]);samples.append(dict(**p,width_m=3.6))
        lanes.append(dict(id=i+1,points=samples))
    voice=narration('city_fog' if bridge.args.profile=='fog' else 'city_rattle')
    if not sc['onset']:
        from voice_bank import narration as regular
        voice=regular('normal',True)
    outcome=sc['outcome'];active=sc['onset'] and not sc['completed'] and outcome['phase']=='idle'
    title=('전방에 안개가 짙어지고 있어요' if bridge.args.profile=='fog' else '차량 아래에서 소리가 들리고 있어요') if sc['onset'] else '주변을 살피며 주행하고 있어요'
    if outcome['phase']!='idle':title='차량이 정차했습니다' if sc['completed'] else '요청한 대응을 진행하고 있어요'
    event=dict(active=active,pending=outcome['phase']!='idle',outcome=outcome,title=title,description=sc['feedback'] if outcome['phase']!='idle' else voice['text'],
        narration=voice,feedback=sc['feedback'],options=options,staged_options=True,hide_eta=True,live_detail=f"현재 속도 {bridge.state.get('speed_kph',0):.0f} km/h")
    sid=sc['session'];points=bridge.scene.route[::3,:2,3].copy();points[:,1]*=-1
    return dict(connected=bridge.state['phase']=='live',schema=2,map='주행 지도',frame=bridge.frame_id,timestamp=time.time(),source='NuRec source-faithful reconstruction',
        actors=actors,road=dict(id=99004,lanes=lanes),lane_width_m=3.6,destinations=[],world_pose=dict(x=tr.location.x,y=tr.location.y,yaw=tr.rotation.yaw),
        ego=dict(id=bridge.ego.id,role='nurec_source_ego',speed_kmh=bridge.state.get('speed_kph',0),lane_index=1,lane_count=2,forward_m=0,right_m=0,up_m=-.4,yaw_deg=0),
        route=dict(destination=dict(id='source_end',name='목적지',detail='경로 안내',point=points[-1].tolist()),points=points.tolist(),index=0,
            remaining_m=max(0,round(route.length-bridge.scenario.ego_s)),arrived=False,off_route=False),
        session=dict(session_id=sid,stage='running' if sc['elapsed_s']>0 else 'ready',navigation=dict(id=sid+'-weaving',status='monitoring',map_label='주행 지도',research_event=event)),
        nurec=dict(bridge.state,scenario=sc),renderer='NuRec RGB')
