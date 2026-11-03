"""Night reconstruction + an explicitly scripted native pedestrian.

The crossing and pedestrian are experimental additions, not recorded people or
an inferred crossing from the source HD map. Original traffic is not relocated.
"""
import math
from types import SimpleNamespace
import numpy as np
from scenario2 import Route
from pedestrian_yield import YieldScenario, OPTIONS, navigation_state as native_navigation
from high_beam import HighBeamSignal


class CrossingAdapter:
    width=3.6
    lane_offsets=(-3.6,0.,3.6)
    def __init__(self,route,cross_s=42.):
        self.route=route;self.length=route.length;self.cross_s=cross_s
        self.curb_right=5.0;self.curb_left=-4.5
        self.points=route.points.copy();self.points[:,1]*=-1

    def sample(self,s,offset=0.):
        pose=self.route.sample(s,lateral=-offset,height=0.)
        xyz=pose[:3,3].copy();xyz[1]*=-1
        return xyz,-math.atan2(pose[1,0],pose[0,0])


class NightPedestrian(YieldScenario):
    SOURCE_FAITHFUL=True
    HYBRID_PEDESTRIAN=True
    TRACK_ID='source_traffic'
    profile='night_pedestrian'
    def __init__(self,matrices,path,proxy_ids):
        self.route=Route(matrices);self.crossing_route=CrossingAdapter(self.route)
        self.source_proxy_ids=set(proxy_ids);self.nearest_gap=None;self.pedestrian=None
        super().__init__(path,self.crossing_route)

    def reset(self,enabled=None):
        super().reset(True)
        self.high_beam=HighBeamSignal();self.collision_count=0;self.ego_s=0.

    def advance(self,dt,driving,ego_xy,speed):
        self.ego_s=self.route.project(ego_xy)
        self.tick_yield(dt,driving,speed,self.ego_s,self.pedestrian.offset() if self.pedestrian else None)
        self.high_beam.advance(dt,driving)
        return self.target_speed()

    def interaction(self,action,session):
        result=super().interaction(action,session)
        if action=='highbeam':
            with self.lock:self.high_beam.begin()
            return self.public()
        return result

    def public(self):
        value=super().public()
        if hasattr(self,'high_beam'):value['high_beam']=self.high_beam.public()
        value['state_source']='NuRec night source + scripted CARLA walker and added crossing; not perception output'
        return value

    def pose(self):return None,0.,0.


def navigation_state(bridge):
    adapter=SimpleNamespace(ego=bridge.ego,scenario=bridge.scenario,
        route=bridge.scenario.crossing_route,pedestrian=bridge.scenario.pedestrian,
        ego_s=bridge.scenario.ego_s,state=dict(bridge.state,frame=bridge.frame_id))
    value=native_navigation(adapter,OPTIONS)
    value.update(map='야간 주행 지도',renderer='NuRec night + CARLA pedestrian',
        source='Hybrid research scene: recorded night background, added native walker/crossing')
    return value
