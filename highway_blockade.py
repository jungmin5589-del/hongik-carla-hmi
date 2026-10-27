"""Four-lane controlled blockade using native reconstructed traffic, not YOLO."""
import math
import time
import numpy as np
from scenario2 import Scenario2
from high_beam import HighBeamSignal


class HighwayBlockade(Scenario2):
    TYPE_ID='congestion_long'
    ONSET_SECONDS=10.
    BASE_GAP=7.
    WIDE_GAP=26.
    SUPPRESS_OTHER_TRAFFIC=True
    LEAD_SPEED=30./3.6
    FAST_SPEED=90./3.6
    FAST_SPACING=20.
    LANE_WIDTH=3.6
    LARGE_OFFSETS=(-10.,4.5,-8.)
    SPEED_PHASES=(0.,.9,1.3,1.9)

    def __init__(self,route,event_path,config):
        self.config=config;self.TRACK_ID=config['lead_track_id']
        self.large_ids=config['large_track_ids'];self.fast_ids=config['fast_track_ids']
        if len(self.large_ids)!=3 or len(self.fast_ids)<8:raise ValueError('Traffic configuration is incomplete')
        self.duration=math.ceil((np.linalg.norm(np.diff(route[:,:2,3],axis=0),axis=1).sum()-35)/self.LEAD_SPEED+7)
        super().__init__(route,event_path)

    def reset(self,enabled=None):
        super().reset(enabled)
        with self.lock:
            self.lead_s=16.;self.lead_speed=0.
            self.large_s=[self.lead_s+offset for offset in self.LARGE_OFFSETS]
            self.large_speeds=[0.,0.,0.]
            self.high_beam=HighBeamSignal()
            self.log('four_lane_ready',slow_speed_range_kph=[25,35],fast_target_kph=90,
                     right_large_count=3,fast_spacing_m=self.FAST_SPACING,finite_route=True)

    def slow_speed(self,phase,position):
        # Different smooth phases create a shifting wall, without lane weaving.
        # Cruise remains 25..35; departure and route-end braking are separate.
        u=min(1.,self.elapsed/4.);ramp=u*u*(3-2*u)
        target=(30.+5.*math.sin(2.*math.pi*max(0.,self.elapsed-4.)/12.+phase))/3.6
        remaining=max(0.,self.route.length-12.-position)
        return min(target*ramp,math.sqrt(2.*1.7*remaining))

    def advance(self,dt,driving,ego_xy,speed):
        with self.lock:
            self.ego_s=self.route.project(ego_xy)
            self.high_beam.advance(dt,self.enabled and driving and not self.completed)
            if self.last_action=='highbeam' and self.high_beam.finished and not self.action_complete:
                self.action_complete=True
                self.feedback='상향등을 두 번 켰다가 껐어요. 앞차와 주변 차량의 저속 흐름은 계속됩니다.'
                self.log('action_completed',action='highbeam',rendered_stages=4)
            if self.enabled and driving and not self.completed:
                step=min(max(dt,0.),.2);self.elapsed+=step
                remaining=max(0.,self.route.length-12.-self.lead_s)
                self.lead_speed=self.slow_speed(self.SPEED_PHASES[0],self.lead_s)
                self.lead_s=min(self.route.length-12.,self.lead_s+self.lead_speed*step)
                if remaining<.1:self.lead_speed=0.
                for i,phase in enumerate(self.SPEED_PHASES[1:]):
                    self.large_speeds[i]=self.slow_speed(phase,self.large_s[i])
                    self.large_s[i]=min(self.route.length-12.,self.large_s[i]+self.large_speeds[i]*step)
                # The two trucks sharing lane 3 must never merge at the end.
                follower,leader=0,1
                a=self.config['vehicles'][self.large_ids[follower]]['size'][0]
                b=self.config['vehicles'][self.large_ids[leader]]['size'][0]
                limit=self.large_s[leader]-(a+b)/2.-1.8
                if self.large_s[follower]>limit:
                    self.large_s[follower]=limit
                    self.large_speeds[follower]=min(self.large_speeds[follower],self.large_speeds[leader])
                if not self.onset and self.elapsed>=self.ONSET_SECONDS:
                    self.onset=True;self.onset_monotonic=time.monotonic();self.log('blocked_traffic_started')
            self.gap=max(0.,self.lead_s-self.ego_s-self.half_length-1.85)
            if self.last_action=='widen' and not self.action_complete and self.gap>=self.desired_gap-.5:
                self.action_complete=True
                self.feedback='감속해 앞차 간격을 넓혔어요. 왼쪽 고속 흐름과 오른쪽 대형차는 계속 주행합니다.'
                self.log('action_completed',action='widen',gap_m=self.gap)
            complete=self.lead_s>=self.route.length-12.1 and speed<.5 and self.gap<=self.desired_gap+3
            return self.finish_advance(dt,driving,speed,complete)

    def interaction(self,action,session):
        if action!='highbeam':return super().interaction(action,session)
        with self.lock:
            if session!=self.session or not self.enabled or not self.onset:raise ValueError('현재 알림에서 다시 선택해 주세요.')
            self.require_action_available()
            if not self.dialog_open:raise ValueError('상황 창을 먼저 열어 주세요.')
            self.last_action='highbeam';self.action_complete=False;self.high_beam.begin()
            self.feedback='상향등을 두 번 켰다가 끄며 앞차의 반응을 살펴봅니다.'
            self.log('action_selected',action=action,since_onset_s=time.monotonic()-self.onset_monotonic)
            self.outcome.begin(action)
            return self.public()

    def acknowledge_high_beam(self,session,sequence,stage):
        with self.lock:
            if session==self.session:self.high_beam.acknowledge(sequence,stage)

    def target_speed(self):
        if not self.enabled:return None
        return max(0.,min(36.,(self.lead_speed+.45*(self.gap-self.desired_gap))*3.6))

    def pose(self):
        with self.lock:return self.route.sample(self.lead_s,height=self.height),0.,0.

    def traffic_specs(self):
        specs=[dict(track_id=self.TRACK_ID,role='slow_lead',lane=2,offset=0.,s=self.lead_s,speed=self.lead_speed)]
        for i,(track,lane) in enumerate(zip(self.large_ids,[3,3,4])):
            specs.append(dict(track_id=track,role='right_large',lane=lane,offset=-(lane-2)*self.LANE_WIDTH,
                              s=self.large_s[i],speed=self.large_speeds[i]))
        # Recycle only outside the route/camera region. Each visible car moves at 90 km/h.
        cycle=len(self.fast_ids)*self.FAST_SPACING
        for idx,track in enumerate(self.fast_ids):
            distance=(idx*self.FAST_SPACING+self.FAST_SPEED*self.elapsed-self.ego_s)%cycle+self.ego_s-60.
            specs.append(dict(track_id=track,role='fast_left',lane=1,offset=self.LANE_WIDTH,
                              s=distance,speed=self.FAST_SPEED))
        return specs

    def traffic_poses(self):
        result={}
        for spec in self.traffic_specs():
            if not -50.<spec['s']<self.route.length+100.:continue
            size=self.config['vehicles'][spec['track_id']]['size']
            s=float(np.clip(spec['s'],0,self.route.length))
            pose=self.route.sample(s,spec['offset'],height=size[2]/2)
            pose[:3,3]+=pose[:3,0]*(spec['s']-s)
            result[spec['track_id']]=pose
        return result

    def public(self):
        with self.lock:
            result=super().public()
            result.update(id=self.TYPE_ID,layout='four_lane_blockade',lane_count=4,ego_lane=2,
                duration_s=self.duration,remaining_s=round(max(0.,(self.route.length-12-self.lead_s)/self.LEAD_SPEED+3)),
                lead_speed_kph=round(self.lead_speed*3.6,1),fast_target_kph=90,right_large_count=3,
                slow_speed_range_kph=[25,35],fast_spacing_m=self.FAST_SPACING,target_gap_m=self.desired_gap,
                high_beam=self.high_beam.public(),
                traffic=[dict(track_id=s['track_id'],role=s['role'],lane=s['lane'],s=round(s['s'],3),speed_kph=round(s['speed']*3.6,1)) for s in self.traffic_specs()],
                finite_route=True,state_source='scripted native reconstructed vehicles with matching CARLA proxies; not perception')
            return result
