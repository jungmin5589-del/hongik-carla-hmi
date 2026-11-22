"""NuRec-only continuous stimuli; leave the native CARLA trials unchanged."""
import copy
import math
import time
from highway_blockade import HighwayBlockade
from night_weaving import BoundaryWeaving
from traffic_intro import blend as _blend

def transition(a,b,start,end,t):
    return _blend(a,b,t,start,end)

def expanded_fleet(config):
    result=copy.deepcopy(config)
    # Reuse licensed assets already present in this installation. No model is
    # downloaded or fabricated; only instance IDs and trajectories are new.
    originals=list(result['large_track_ids'])
    for i in range(3):
        key=str(22101+i);source=originals[i]
        result['vehicles'][key]=copy.deepcopy(result['vehicles'][source])
        spec=next(s for s in result['insert_assets'] if s['id']==source)
        result['insert_assets'].append(dict(spec,id=key))
        result['large_track_ids'].append(key)
    originals=list(result['fast_track_ids'])
    while len(result['fast_track_ids'])<24:
        i=len(result['fast_track_ids']);source=originals[i%len(originals)];key=str(25101+i)
        result['vehicles'][key]=copy.deepcopy(result['vehicles'][source])
        spec=next(s for s in result['insert_assets'] if s['id']==source)
        result['insert_assets'].append(dict(spec,id=key));result['fast_track_ids'].append(key)
    return result

class NaturalBlockade(HighwayBlockade):
    ONSET_SECONDS=30.
    FAST_SPACING=13.
    BASE_GAP=6.5

    def __init__(self,route,event_path,config):
        config=expanded_fleet(config)
        # Parent validates its historical three source truck IDs, then dispatches
        # reset virtually. Configure all six only after the source check.
        large=config['large_track_ids'];config['large_track_ids']=large[:3]
        super().__init__(route,event_path,config)
        self.large_ids=large;self.config['large_track_ids']=large;self.reset()

    def reset(self,enabled=None):
        super().reset(enabled)
        self.lead_s=24.+self.half_length+1.85;self.desired_gap=24.
        self.large_s=[self.lead_s+48.-15.*(i%3)+(6. if i>=3 else 0.) for i in range(len(self.large_ids))]
        self.large_speeds=[0.]*len(self.large_ids)
        self.fast_s=[-80.+i*self.FAST_SPACING for i in range(len(self.fast_ids))]

    def slow_speed(self,phase,position):
        ramp=transition(0.,1.,0.,12.,self.elapsed)
        variation=transition(0.,1.,30.,45.,self.elapsed)
        target=35.+variation*(-5.+5.*math.sin(2*math.pi*max(0.,self.elapsed-30.)/12.+phase))
        return min(target/3.6*ramp,math.sqrt(2.*1.7*max(0.,self.route.length-12.-position)))

    def advance(self,dt,driving,ego_xy,speed):
        with self.lock:
            self.ego_s=self.route.project(ego_xy)
            self.high_beam.advance(dt,driving and not self.completed)
            if self.enabled and driving and not self.completed:
                step=min(.2,max(0.,dt));self.elapsed+=step
                if self.last_action!='widen':self.desired_gap=transition(24.,self.BASE_GAP,30.,45.,self.elapsed)
                self.lead_speed=self.slow_speed(0.,self.lead_s)
                self.lead_s=min(self.route.length-12.,self.lead_s+self.lead_speed*step)
                for i in range(len(self.large_ids)):
                    ordinary=self.slow_speed(i*.8,self.large_s[i])
                    target=self.lead_s+18.-15.*(i%3)+(6. if i>=3 else 0.)
                    formation=max(25./3.6,min(35./3.6,self.lead_speed+.28*(target-self.large_s[i])+.25*math.sin(self.elapsed*.5+i)))
                    self.large_speeds[i]=transition(ordinary,formation,30.,45.,self.elapsed)
                    self.large_speeds[i]=min(self.large_speeds[i],math.sqrt(2*1.7*max(0.,self.route.length-12.-self.large_s[i])))
                    self.large_s[i]=min(self.route.length-12.,self.large_s[i]+self.large_speeds[i]*step)
                for i in range(len(self.large_ids)):
                    if i%3==0:continue
                    ahead=i-1
                    a=self.config['vehicles'][self.large_ids[i]]['size'][0]
                    b=self.config['vehicles'][self.large_ids[ahead]]['size'][0]
                    limit=self.large_s[ahead]-(a+b)/2.-2.
                    if self.large_s[i]>limit:
                        self.large_s[i]=limit;self.large_speeds[i]=min(self.large_speeds[i],self.large_speeds[ahead])
                fast=transition(55.,90.,30.,42.,self.elapsed)/3.6
                cycle=len(self.fast_ids)*self.FAST_SPACING
                for i in range(len(self.fast_s)):
                    self.fast_s[i]+=fast*step
                    # The 24-car pool wraps beyond +232m, reinserting behind
                    # -80m. Never wrap a visible 70m-ahead vehicle into view.
                    if self.fast_s[i]-self.ego_s>cycle-80.:
                        destination=self.fast_s[i]-cycle
                        if destination<self.ego_s-60. and all(abs(destination-other)>9. for j,other in enumerate(self.fast_s) if j!=i):
                            self.fast_s[i]=destination
                if not self.onset and self.elapsed>=self.ONSET_SECONDS:
                    self.onset=True;self.onset_monotonic=time.monotonic();self.log('blocked_traffic_started')
            self.gap=max(0.,self.lead_s-self.ego_s-self.half_length-1.85)
            if self.last_action=='widen' and not self.action_complete and self.gap>=self.desired_gap-.5:
                self.action_complete=True
            complete=self.lead_s>=self.route.length-12.1 and speed<.5 and self.gap<=self.desired_gap+3
            return self.finish_advance(dt,driving,speed,complete)

    def traffic_specs(self):
        result=[dict(track_id=self.TRACK_ID,role='slow_lead',lane=2,offset=0.,s=self.lead_s,speed=self.lead_speed)]
        for i,track in enumerate(self.large_ids):
            lane=3+i//3
            result.append(dict(track_id=track,role='right_large',lane=lane,offset=-(lane-2)*3.6,s=self.large_s[i],speed=self.large_speeds[i]))
        fast=transition(55.,90.,30.,42.,self.elapsed)/3.6
        for i,track in enumerate(self.fast_ids):
            result.append(dict(track_id=track,role='fast_left',lane=1,offset=3.6,s=self.fast_s[i],speed=fast))
        return result

    def public(self):
        state=super().public();state.update(right_large_count=len(self.large_ids),intro_seconds=30.,natural_motion=True)
        return state

class NaturalWeaving(BoundaryWeaving):
    ONSET_SECONDS=30.
    LEAD_SPEED=30./3.6
    BASE_GAP=6.5

    def reset(self,enabled=None):
        super().reset(enabled)
        self.lead_s=24.+self.half_length+1.85;self.gap=self.desired_gap=24.;self.lead_speed=0.
        # A shorter captured street cannot support highway speed for a 30s
        # introduction plus an observation period. Pace within the real source,
        # never extend the road or loop an unseen background.
        self.cruise_kph=min(35.,max(3.6,(self.route.length-self.lead_s-20.)*3.6/75.))

    def advance(self,dt,driving,ego_xy,speed):
        with self.lock:
            if driving and not self.completed:
                self.lead_speed=transition(0.,1.,0.,12.,self.elapsed)*transition(self.cruise_kph,min(30.,self.cruise_kph),30.,42.,self.elapsed)/3.6
                self.lead_speed=min(self.lead_speed,math.sqrt(2*1.7*max(0.,self.route.length-8.-self.lead_s)))
                if self.last_action!='widen':self.desired_gap=transition(24.,self.BASE_GAP,30.,42.,self.elapsed)
            # The parent movement uses LEAD_SPEED; temporarily supply the actual
            # continuous speed, while retaining the calibrated route/heading.
            self.LEAD_SPEED=max(.01,self.lead_speed)
            return super().advance(dt,driving,ego_xy,speed)

    def target_speed(self):
        if not self.enabled:return None
        return max(0.,min(36.,(self.lead_speed+.5*(self.gap-self.desired_gap))*3.6))

    def public(self):
        state=super().public();state.update(intro_seconds=30.,natural_motion=True,lead_speed_kph=round(self.lead_speed*3.6,1),source_cruise_cap_kph=round(self.cruise_kph,1))
        return state
