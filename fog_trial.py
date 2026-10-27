"""Five-minute finite drive, external fog starts at 30 driving seconds."""
import math
import time
import numpy as np
from scenario2 import Scenario2
from fog_scene import LEAD_TRACK_ID,CONTEXT_TRACK_IDS


def smooth(value):
    x=float(np.clip(value,0.,1.))
    return x*x*(3.-2.*x)


def fog_at(seconds):
    # Continuous optical extinction, not a claimed measured visibility distance.
    keys=[30.,65.,130.,220.,300.]
    betas=[0.,.025,.085,.18,.25]
    beta=0.
    for i in range(len(keys)-1):
        if seconds>=keys[i]:
            u=smooth((seconds-keys[i])/(keys[i+1]-keys[i]))
            beta=betas[i]+u*(betas[i+1]-betas[i])
    stage=('clear' if seconds<=30 else 'developing' if seconds<65 else
           'thick' if seconds<130 else 'dense' if seconds<220 else 'whiteout')
    return dict(stage=stage,beta=beta,strength=beta/.25,onset_s=30.)


class DenseFog(Scenario2):
    ONSET_SECONDS=30.
    BASE_GAP=14.
    WIDE_GAP=36.
    SUPPRESS_OTHER_TRAFFIC=True
    TYPE_ID='dense_fog'
    CALIBRATE_LEAD_HEIGHT=True
    context_track_ids=CONTEXT_TRACK_IDS

    def __init__(self,route,event_path,track_id=LEAD_TRACK_ID):
        self.TRACK_ID=str(track_id)
        self.duration=300
        super().__init__(route,event_path)

    def reset(self,enabled=None):
        super().reset(enabled)
        with self.lock:
            self.lead_s=24.
            self.lead_speed=0.
            self.extra_caution=False
            self.stop_requested=False
            self.last_stage='clear'
            self.times=np.linspace(0.,300.,3001)
            t=self.times
            u=np.clip((t-30.)/210.,0.,1.)
            envelope=(1.-.65*u*u*(3.-2.*u))
            start=np.clip(t/5.,0.,1.);end=np.clip((288.-t)/12.,0.,1.)
            envelope*=start*start*(3.-2.*start)*end*end*(3.-2.*end)
            integral=np.r_[0.,np.cumsum((envelope[:-1]+envelope[1:])*.05)]
            travel=self.route.length-10.-self.lead_s
            self.positions=self.lead_s+integral*travel/integral[-1]
            self.speeds=envelope*travel/integral[-1]
            self.log('fog_trial_ready',duration_s=300,fog_onset_s=30.,loop=False)

    def advance(self,dt,driving,ego_xy,speed):
        with self.lock:
            self.ego_s=self.route.project(ego_xy)
            if self.enabled and driving and not self.completed:
                self.elapsed+=min(max(dt,0.),.2)
                self.lead_s=float(np.interp(self.elapsed,self.times,self.positions))
                self.lead_speed=float(np.interp(self.elapsed,self.times,self.speeds))
                if not self.onset and self.elapsed>=30.:
                    self.onset=True;self.onset_monotonic=time.monotonic()
                    self.log('fog_started')
                stage=fog_at(self.elapsed)['stage']
                if stage!=self.last_stage:
                    self.last_stage=stage;self.log('fog_stage_changed',stage=stage)
            baseline=14.+10.*smooth((self.elapsed-30.)/140.)
            self.desired_gap=max(baseline,self.WIDE_GAP if self.extra_caution else baseline)
            self.gap=max(0.,self.lead_s-self.ego_s-self.half_length-1.85)
            if self.last_action=='widen' and not self.action_complete and self.gap>=self.desired_gap-.5:
                self.action_complete=True
                self.feedback='앞차와의 간격을 넓혔어요. 여유를 두고 천천히 주행합니다.'
                self.log('action_completed',action='widen',gap_m=self.gap)
            complete=bool(self.elapsed>=300. and speed<1. and abs(self.gap-self.desired_gap)<3.)
            return self.finish_advance(dt, driving, speed, complete)

    def target_speed(self):
        if not self.enabled:return None
        return max(0.,min(25.,(self.lead_speed+.35*(self.gap-self.desired_gap))*3.6))

    def pose(self):
        with self.lock:return self.route.sample(self.lead_s,height=self.height),0.,0.

    def interaction(self,action,session):
        with self.lock:
            if action in ('notification_exposed','open','close'):
                return super().interaction(action,session)
            if session!=self.session or not self.enabled or not self.onset or not self.dialog_open:
                raise ValueError('현재 안개 알림에서 다시 선택해 주세요.')
            if action not in ('inspect','widen','stop_request'):
                raise ValueError('이 조건에서 사용할 수 없는 요청입니다.')
            self.require_action_available()
            self.last_action=action;self.action_complete=action=='inspect'
            if action=='inspect':
                self.feedback=f'현재 앞차 간격은 약 {round(self.gap)}미터입니다. 감속하며 간격을 확인하고 있어요.'
            elif action=='widen':
                self.extra_caution=True;self.desired_gap=self.WIDE_GAP
                self.feedback='서서히 감속하며 앞차와의 간격을 더 넓히고 있어요.'
            else:
                self.extra_caution=True;self.desired_gap=self.WIDE_GAP;self.stop_requested=True
                self.feedback='현재 구간에 확인된 정차 공간이 없어 우선 더 감속하며 간격을 확보합니다.'
            self.log('action_applied',action=action,feedback=self.feedback,safe_stop_verified=False)
            self.outcome.begin(action)
            return self.public()

    def public(self):
        with self.lock:
            result=super().public()
            result.update(id=self.TYPE_ID,duration_s=300,remaining_s=round(max(0.,300.-self.elapsed)),
                lead_speed_kph=round(self.lead_speed*3.6,1),fog=fog_at(self.elapsed),
                stop_requested=self.stop_requested,safe_stop_verified=False,
                state_source='scripted external fog, actual CARLA control, approximate reconstructed range')
            return result
