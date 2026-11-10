"""Standalone CARLA-rendered passenger trials. Never loads NuRec/WSL models."""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import carla
import numpy as np
from PIL import Image
from io import BytesIO

from action_outcome import ActionOutcome
from navigation_adapter import NavigationAdapter, navigation_html, static_asset
from native_carla_route import HighwayRoute, steering, fog_density, curve_speed_limit
from native_alignment import route_atlas, route_index, start_alignment, steering_geometry, tracking_alignment, ego_lane
from scenario2 import Scenario2
from voice_bank import narration, audio_path
from pedestrian_yield import CrossingRoute, YieldScenario, YieldActor, OPTIONS as YIELD_OPTIONS, navigation_state as yield_navigation_state
from pedestrian_voice import audio_path as pedestrian_audio_path
from city_voice import audio_path as city_audio_path
from city_scenarios import ContextScenario, ExteriorActor, OPTIONS as CONTEXT_OPTIONS, navigation_state as context_navigation_state, find_shoulder
from midterm_study import StudyMixin, OPTIONS as MIDTERM_OPTIONS, option as study_option, enrich_navigation
from passenger_music import library as music_library, stream as stream_music
from fallen_cargo import CargoScenario, CargoActor, OPTIONS as CARGO_OPTIONS, navigation_state as cargo_navigation_state, left_lane_clear, following_speed
from lab_settings import sun_altitude
from research_store import ResearchStore

ROOT = Path(__file__).resolve().parent
PORT, RPC = 8774, 2026
PROFILES = {'congestion': '4차로 정체', 'night': '야간 졸음운전 차량', 'fog': '짙은 안개', 'yield': '보행자와 서로 양보',
            'carpool':'카풀 대기 중 외부인 접근','rattle':'주행 중 반복되는 이상음','cargo':'도로 위 낙하물'}
SIZES = {'smooth': (640, 360), 'balanced': (960, 540), 'high': (1280, 720), 'fullhd': (1920, 1080)}


class NativeScenario(Scenario2):
    def __init__(self, profile, event_path):
        self.profile = profile
        self.TYPE_ID = 'congestion_long' if profile == 'congestion' else 'dense_fog' if profile == 'fog' else 'drowsy_night'
        if profile == 'congestion':self.FAST_SPEED=25.
        self.BASE_GAP = 8. if profile == 'fog' else 6.5 if profile == 'night' else 9.
        self.WIDE_GAP = 36. if profile == 'fog' else 28.
        self.ONSET_SECONDS = 10.
        self.lock = threading.RLock()
        self.events = open(event_path, 'a', encoding='utf-8', buffering=1)
        self.enabled = True
        self.reset()

    def reset(self, enabled=None):
        super().reset(enabled)
        self.gap = self.BASE_GAP
        self.highbeam_at = None
        self.highbeam_on = False
        self.actual_elapsed = 0.
        self.collision_count = 0

    def tick(self, dt, driving, speed, gap):
        with self.lock:
            self.gap = gap
            if driving and not self.completed:
                self.elapsed += dt
                if not self.onset and self.elapsed >= self.ONSET_SECONDS:
                    self.onset = True
                    self.onset_monotonic = time.monotonic()
                    self.log('scenario_onset', renderer='CARLA RGB', profile=self.profile)
            if self.highbeam_at is not None:
                since = self.elapsed-self.highbeam_at
                self.highbeam_on = (0 <= since < .6) or (1.1 <= since < 1.7)
                if since >= 1.7:
                    self.action_complete = True
            if self.last_action in ('widen', 'stop_request') and gap >= self.desired_gap-.5:
                self.action_complete = True
            self.outcome.tick(dt, driving, speed, self)
            if self.outcome.phase == 'complete':
                self.completed, self.completion_reason = True, 'action_outcome'
                self.feedback = self.outcome.summary
            if self.elapsed >= 300 and not self.outcome.active and speed < .5 and not self.completed:
                self.completed, self.completion_reason = True, 'duration_end'
                self.log('trial_completed',reason='duration_end',speed_kph=speed)

    def interaction(self, action, session):
        if action not in ('highbeam', 'inspect', 'stop_request'):
            return super().interaction(action, session)
        with self.lock:
            if session != self.session or not self.onset or not self.dialog_open:
                raise ValueError('현재 상황 설명을 연 뒤 실행해 주세요.')
            self.require_action_available()
            self.last_action = action
            self.action_complete = action == 'inspect'
            if action == 'highbeam':
                self.highbeam_at = self.elapsed
                self.feedback = '상향등을 두 번 점멸하고 주변 흐름을 확인합니다.'
            elif action == 'stop_request':
                self.desired_gap = self.WIDE_GAP
                self.feedback = '정차 가능한 갓길을 확인하지 못해 우선 감속하고 간격을 확보합니다.'
            else:
                self.feedback = '현재 속도·차간 거리와 감속 상태를 확인했습니다.'
            self.outcome.begin(action)
            self.log('action_applied', action=action, target_gap_m=self.desired_gap)
            return self.public()

    def public(self):
        with self.lock:
            result = dict(id=self.TYPE_ID, session=self.session, enabled=True, onset=self.onset,
                          elapsed_s=round(self.elapsed, 2), duration_s=300, remaining_s=max(0,300-self.elapsed),
                          gap_m=round(self.gap, 2), target_gap_m=self.desired_gap, horn_count=self.horn_count,
                          collision_count=self.collision_count,
                          action=self.last_action, action_complete=self.action_complete, feedback=self.feedback,
                          completed=self.completed, completion_reason=self.completion_reason,
                          outcome=self.outcome.public(), dialog_open=self.dialog_open,
                          high_beam=dict(on=self.highbeam_on),
                          state_source='CARLA actor state and scripted stimulus; not perception inference')
            if self.profile == 'congestion':
                result['layout'] = 'four_lane_blockade'
            elif self.profile == 'night':
                result['layout'] = 'two_lane_boundary_weaving'
            else:
                density = fog_density(self.elapsed)
                result['fog'] = dict(density=density, stage='clear' if density==0 else 'dense' if density>95 else 'thick')
            return result


class StudyNative(StudyMixin, NativeScenario):pass
class StudyContext(StudyMixin, ContextScenario):pass
class StudyCargo(StudyMixin, CargoScenario):pass
class StudyYield(StudyMixin, YieldScenario):
    def tick_yield(self,*args,**kwargs):
        super().tick_yield(*args,**kwargs)
        if self.study.phase not in ('idle','complete') and self.completed:
            self.completed=False;self.completion_reason=None;self.outcome.phase='managed'
            self.phase='finishing'


class NativeNavigation(NavigationAdapter):
    def options(self):
        from navigation_adapter import BLOCKADE_OPTIONS, OPTIONS, FOG_OPTIONS
        if getattr(self.bridge,'presentation',None)=='midterm' and getattr(self.bridge.scenario,'study',None):
            if self.bridge.condition=='A':return []
            return [*MIDTERM_OPTIONS[self.bridge.profile],study_option('maintain','그냥 둘게요','현재 차량의 대응을 유지해요.')]
        if self.bridge.profile == 'cargo':return CARGO_OPTIONS
        if self.bridge.profile == 'yield':return YIELD_OPTIONS
        if self.bridge.profile in CONTEXT_OPTIONS:return CONTEXT_OPTIONS[self.bridge.profile]
        return BLOCKADE_OPTIONS if self.bridge.profile == 'congestion' else FOG_OPTIONS if self.bridge.profile == 'fog' else OPTIONS

    def atlas(self):
        r=self.bridge.route
        if r is None:return dict(map='CARLA',roads=[],destinations=[],buildings=[])
        if self.atlas_cache is None:
            name='CARLA Town03' if self.bridge.profile in ('yield','carpool') else 'CARLA Town04'
            self.atlas_cache=route_atlas(r,name)
        return self.atlas_cache

    def state(self):
        data=self.raw_state()
        if data.get('connected'):
            index,count=ego_lane(data.get('road',{}).get('lanes',[]))
            data['ego'].update(lane_index=index,lane_count=count)
            wp=self.bridge.road_map.get_waypoint(self.bridge.ego.get_location(),project_to_road=False,lane_type=carla.LaneType.Any)
            if wp:data['ego']['lane_type']=str(wp.lane_type)
        return enrich_navigation(data,self.bridge)

    def raw_state(self):
        b = self.bridge
        if b.ego is None or b.scenario is None:
            return dict(connected=False, reason=b.state.get('error') or 'CARLA 도로와 차량을 준비하고 있어요.')
        if b.profile=='cargo':return cargo_navigation_state(b,self.options())
        if b.profile=='yield':return yield_navigation_state(b,self.options())
        if b.profile in CONTEXT_OPTIONS:return context_navigation_state(b,self.options())
        tr, sc = b.ego.get_transform(), b.scenario.public()
        yaw = math.radians(tr.rotation.yaw)
        def local(x,y,angle=0):
            dx,dy=x-tr.location.x,y-tr.location.y
            return dict(forward_m=dx*math.cos(yaw)+dy*math.sin(yaw),
                        right_m=-dx*math.sin(yaw)+dy*math.cos(yaw),up_m=-.4,
                        yaw_deg=(angle-tr.rotation.yaw+180)%360-180)
        lanes=[]
        for i in range(4):
            samples=[]
            for d in range(-25,141,4):
                p,a=b.route.sample(b.ego_s+d,(i-1)*b.route.width)
                samples.append(dict(**local(p[0],p[1],math.degrees(a)),width_m=b.route.width))
            lanes.append(dict(id=i+1,points=samples))
        actors=[]
        for item in b.vehicles[1:]:
            at=item['actor'].get_transform();p=local(at.location.x,at.location.y,at.rotation.yaw)
            if not -45<p['forward_m']<180 or abs(p['right_m'])>25:continue
            extent=item['extent']
            actors.append(dict(id=item['actor'].id,kind='vehicle',label='앞차' if item['role']=='lead' else '주변 차량',
                               role='lead' if item['role']=='lead' else 'context',vehicle_type='large' if extent.x>3 else 'car',
                               length_m=extent.x*2,width_m=extent.y*2,height_m=extent.z*2,
                               speed_kmh=item['actor'].get_velocity().length()*3.6,
                               world_pose=dict(x=at.location.x,y=at.location.y,yaw=at.rotation.yaw),**p))
        profile=b.profile;outcome=sc['outcome'];active=sc['onset'] and not sc['completed']
        title={'congestion':'앞과 오른쪽은 느리고 왼쪽은 빠르게 흐르고 있습니다',
               'night':'앞차가 차선 경계 주변에서 좌우로 흔들리고 있습니다',
               'fog':'전방에 안개가 짙어지고 있습니다'}[profile] if active else '주행 상황을 살피고 있습니다'
        voice=narration('blockade' if profile=='congestion' else profile,active,sc['completed'])
        if sc['completed'] and sc['completion_reason']=='duration_end':
            title='차량이 정차했습니다'
            voice=dict(text='차량이 안전하게 정차했습니다. 주변 상황을 확인하고 있습니다.',
                       speaker='Sohee',url=None,cached=False)
        if outcome['phase']!='idle':
            title='차량이 정차했습니다' if sc['completed'] else '요청한 대응을 진행하고 있어요'
            voice=dict(text=outcome['message'] or sc['feedback'],speaker='Sohee',url=None,cached=False)
        event=dict(active=active,pending=outcome['phase']!='idle',outcome=outcome,feedback=sc['feedback'],
                   title=title,description=voice['text'],narration=voice,options=self.options(),
                   live_detail=f"현재 속도 {b.state['speed_kph']:.0f} km/h · 앞차 간격 약 {sc['gap_m']:.1f} m")
        route_points=b.route.points[::3,:2].tolist()
        remain=max(0,round(300-sc['elapsed_s']))
        return dict(connected=b.state['phase']=='live',schema=2,map='CARLA Town04',
                    source='CARLA RGB and actual physical actors; scripted trial',frame=b.state['frame'],timestamp=time.time(),
                    ego=dict(id=b.ego.id,role='native_carla_ego',forward_m=0,right_m=0,up_m=-.4,yaw_deg=0,
                             speed_kmh=b.state['speed_kph'],lane_index=2,lane_count=4,lane_id=-2),
                    road=dict(id=4,lanes=lanes),lane_width_m=b.route.width,actors=actors,destinations=[],
                    world_pose=dict(x=tr.location.x,y=tr.location.y,yaw=tr.rotation.yaw),
                    route=dict(destination=dict(id='trial_end',name='목적지',point=route_points[-1],
                                                distance_m=round(b.route.length),detail='경로 안내'),
                               points=route_points,index=route_index(b.route,b.ego_s),remaining_m=round(remain*30/3.6),
                               arrived=sc['completed'] and sc['completion_reason']=='duration_end',off_route=False),
                    session=dict(session_id=sc['session'],stage='running' if sc['elapsed_s']>0 or b.command['mode']=='auto' else 'ready',
                                 scenario={'congestion':1,'night':2,'fog':3}[profile],
                                 navigation=dict(id=sc['session']+'-weaving',status='monitoring',map_label=PROFILES[profile],
                                                 title=title,body=voice['text'],research_event=event)),
                    nurec=dict(b.state,scenario=sc),renderer='CARLA RGB')


class NativeBridge:
    def __init__(self, quality='high'):
        self.stop=threading.Event();self.lock=threading.RLock();self.frame_event=threading.Condition()
        self.jpeg=None;self.frame_id=0;self.images=queue.Queue(maxsize=1)
        from lab_settings import enabled
        self.state=dict(kind='hongik-native-carla',phase='choose',renderer_backend='carla',error=None,lab_rig=enabled(),
                        mode='paused',quality=quality,width=SIZES[quality][0],height=SIZES[quality][1],
                        speed_kph=0,frames=0,frame=0,target_fps=30,measured_fps=0)
        self.presentation='midterm';self.condition='B'
        self.language='ko';self.research=ResearchStore()
        self.command={'mode':'paused'};self.profile=None;self.scenario=None;self.ego=None
        self.vehicles=[];self.pedestrian=None;self.cargo=None;self.camera=None;self.rig=None;self.collision=None;self.world=None;self.route=None;self.ego_s=100.
        self.pending=queue.Queue();self.navigation=NativeNavigation(self);self.camera_generation=0
        self.run_dir=ROOT/'native-runs'/time.strftime('%Y%m%d-%H%M%S')
        self.run_dir.mkdir(parents=True,exist_ok=True)
        self.trace=(self.run_dir/'telemetry.jsonl').open('a',encoding='utf-8',buffering=1)
        threading.Thread(target=self.encode,daemon=True).start()
        threading.Thread(target=self.run,daemon=True).start()

    def encode(self):
        times=[]
        while not self.stop.is_set():
            try:g,img=self.images.get(timeout=.5)
            except queue.Empty:continue
            if g!=self.camera_generation:continue
            arr=np.frombuffer(img.raw_data,dtype=np.uint8).reshape(img.height,img.width,4)
            output=BytesIO();Image.fromarray(arr[:,:,:3][:,:,::-1]).save(output,format='JPEG',quality=88)
            data=output.getvalue();now=time.monotonic();times=[t for t in times if now-t<3.];times.append(now)
            with self.frame_event:
                if g!=self.camera_generation:continue
                self.jpeg=data;self.frame_id+=1
                self.state.update(frames=self.frame_id,width=img.width,height=img.height,
                                  measured_fps=round((len(times)-1)/max(.01,now-times[0]),1))
                self.frame_event.notify_all()
                rig=self.rig
                if rig:rig.frames.publish('center',img.frame,data)

    def connect(self,profile=None):
        from launch_native_carla import OWNED, CARLA, process_command
        owned=json.loads(OWNED.read_text(encoding='utf-8-sig')) if OWNED.is_file() else {}
        command=process_command(owned.get('carla'))
        if str(CARLA/'CarlaUE4.exe').lower() not in command.lower() or '-carla-rpc-port=2026' not in command:
            raise RuntimeError('이 앱이 시작한 CARLA를 확인하지 못했습니다. 50번 실행 파일을 사용해 주세요.')
        client=carla.Client('127.0.0.1',RPC);client.set_timeout(90.)
        if client.get_client_version().split('-')[0]!=client.get_server_version().split('-')[0]:
            raise RuntimeError('CARLA Python client and server versions must match; use the lab environment for 0.9.15.')
        world=client.get_world()
        target='Town03' if profile in ('yield','carpool') else 'Town04'
        if not world.get_map().name.endswith('/'+target):
            world=client.load_world(target)
        settings=world.get_settings()
        if settings.synchronous_mode:
            raise RuntimeError('The native CARLA world is owned by a synchronous client.')
        if settings.no_rendering_mode:
            settings.no_rendering_mode=False;world.apply_settings(settings)
        self.client=client;self.world=world
        self.road_map=world.get_map()
        self.route=CrossingRoute.build(self.road_map) if profile in ('yield','carpool') else HighwayRoute.build(self.road_map)

    def clear_actors(self):
        self.camera_generation+=1
        if self.rig:self.rig.close();self.rig=None;self.camera=None
        if self.cargo:self.cargo.destroy();self.cargo=None
        if self.pedestrian:self.pedestrian.destroy();self.pedestrian=None
        owned=[self.camera,self.collision,*[v['actor'] for v in self.vehicles]]
        known_ids={actor.id for actor in owned if actor is not None}
        for actor in owned:
            if actor is not None:
                try:
                    if isinstance(actor,carla.Sensor):actor.stop()
                    actor.destroy()
                except RuntimeError:pass
        self.camera=self.collision=self.ego=None;self.vehicles=[]
        if self.world:
            for actor in self.world.get_actors().filter('sensor.camera.rgb'):
                parent=actor.parent
                if actor.attributes.get('role_name','').startswith('hongik_native_') or parent and parent.attributes.get('role_name','').startswith('hongik_native_'):
                    actor.stop();actor.destroy()
            for actor in self.world.get_actors().filter('vehicle.*'):
                if actor.id not in known_ids and actor.attributes.get('role_name','').startswith('hongik_native_'):
                    actor.destroy()
            for actor in self.world.get_actors().filter('walker.*'):
                if actor.attributes.get('role_name','').startswith('hongik_native_'):actor.destroy()
        if self.scenario:self.scenario.events.close()
        self.scenario=None

    def spawn(self, blueprint, s, offset, role, speed=30, color=None):
        bp=self.world.get_blueprint_library().find(blueprint)
        bp.set_attribute('role_name','hongik_native_'+role)
        if color and bp.has_attribute('color'):bp.set_attribute('color',color)
        xyz,yaw=self.route.sample(s,offset)
        actor=self.world.try_spawn_actor(bp,carla.Transform(carla.Location(x=float(xyz[0]),y=float(xyz[1]),z=float(xyz[2]+.45)),
                                                           carla.Rotation(yaw=math.degrees(yaw))))
        if actor is None:raise RuntimeError('Vehicle spawn blocked: '+role)
        # Bounding-box access is a synchronous RPC (~one engine tick). Vehicle
        # dimensions do not change during a run; avoid dozens of RPCs per frame.
        item=dict(actor=actor,extent=actor.bounding_box.extent,s=s,offset=offset,role=role,speed=speed,steer=0.,acc=0.)
        self.vehicles.append(item)
        actor.set_light_state(carla.VehicleLightState(carla.VehicleLightState.Position|carla.VehicleLightState.LowBeam))
        return item

    def setup(self, profile):
        with self.lock:
            self.state.update(phase='preparing',error=None,mode='paused');self.command['mode']='paused'
            self.clear_actors()
            target='Town03' if profile in ('yield','carpool') else 'Town04'
            if self.world is None or not self.world.get_map().name.endswith('/'+target):self.connect(profile)
            self.clear_actors()  # Also recover tagged actors after an app-only restart.
            self.profile=profile;self.ego_s=100.
            with self.frame_event:
                self.jpeg=None;self.frame_id=0;self.state['frames']=0
            event_path=self.run_dir/(uuid.uuid4().hex[:8]+'-events.jsonl')
            self.ego_s=max(2.,self.route.cross_s-36.) if profile=='yield' else 5. if profile=='carpool' else 100.
            offset=3.5 if profile=='carpool' else 0.
            modern=self.presentation=='midterm'
            native_cls,context_cls,yield_cls,cargo_cls=(StudyNative,StudyContext,StudyYield,StudyCargo) if modern else (NativeScenario,ContextScenario,YieldScenario,CargoScenario)
            self.scenario=cargo_cls(event_path) if profile=='cargo' else yield_cls(event_path,self.route) if profile=='yield' else context_cls(profile,event_path,self.ego_s,offset) if profile in CONTEXT_OPTIONS else native_cls(profile,event_path)
            self.research.attach(self.scenario,profile,self.condition,self.language)
            if modern:self.scenario.study.bind(self,self.condition)
            self.state.update(presentation=self.presentation,condition=self.condition)
            if profile=='carpool':
                p,_=self.route.sample(self.ego_s,offset)
                wp=self.world.get_map().get_waypoint(carla.Location(x=float(p[0]),y=float(p[1]),z=float(p[2])),project_to_road=False,lane_type=carla.LaneType.Any)
                if not wp or wp.lane_type!=carla.LaneType.Parking:raise RuntimeError('The waiting location is not a mapped parking area.')
            self.spawn('vehicle.tesla.model3',self.ego_s,offset,'ego',color='35,85,190')
            self.ego=self.vehicles[0]['actor']
            if profile=='yield':
                self.pedestrian=YieldActor(self.world,self.route)
                # This owned experiment uses an unsignalized crossing.
                for light in self.world.get_actors().filter('traffic.traffic_light*'):
                    light.set_state(carla.TrafficLightState.Off);light.freeze(True)
            elif profile=='carpool':self.pedestrian=ExteriorActor(self.world,self.route,self.ego_s)
            elif profile=='cargo':
                self.spawn('vehicle.carlamotors.european_hgv',self.ego_s+22.,0.,'cargo_truck',25.)
                self.cargo=CargoActor(self.world,self.route)
                self.cargo.prepare(self.vehicles[1]['actor'],self.vehicles[1]['s'])
                self.scenario.actor_id=self.cargo.actor.id
                self.scenario.log('cargo_loaded',actor_id=self.cargo.actor.id)
            elif profile=='rattle':self.scenario.shoulder_offset=find_shoulder(self.route,self.world.get_map(),self.ego_s+35.)
            else:self.spawn('vehicle.nissan.micra',100+self.scenario.BASE_GAP+4.2,0.,'lead',color='220,223,226')
            if profile=='congestion':
                for s,offset in [(102.,self.route.width),(120.,2*self.route.width),(86.,2*self.route.width)]:
                    self.spawn('vehicle.carlamotors.european_hgv',s,offset,'truck',30)
                for i in range(14):
                    self.spawn('vehicle.audi.a2' if i%2 else 'vehicle.tesla.model3',-40+i*23.,-self.route.width,'fast',90,
                               color=['185,189,193','45,49,55','214,216,219'][i%3])
            weather=carla.WeatherParameters(cloudiness=15,precipitation=0,sun_altitude_angle=sun_altitude(profile),
                                           fog_density=0,fog_distance=0,fog_falloff=.1,wetness=0)
            self.world.set_weather(weather)
            # Let every suspension settle before showing the ready state.
            for v in self.vehicles:v['actor'].apply_control(carla.VehicleControl(brake=1,hand_brake=True))
            for _ in range(16):self.world.wait_for_tick(2.)
            settled=0;deadline=time.monotonic()+6.
            while time.monotonic()<deadline:
                alignment=start_alignment(self.route,self.vehicles)
                settled=settled+1 if alignment['ready'] else 0
                if settled>=4:break
                self.world.wait_for_tick(2.)
            self.state['departure_alignment']=alignment
            if settled<4:
                raise RuntimeError('출발 위치·방향 정렬을 확인하지 못했습니다. 다시 준비해 주세요.')
            for item in self.vehicles:
                item['geometry']=steering_geometry(item['actor'])
                item['rest_z']=item['actor'].get_location().z-self.route.sample(item['s'],item['offset'])[0][2]
            self.make_camera(self.state['quality'])
            sensor=self.world.get_blueprint_library().find('sensor.other.collision')
            self.collision=self.world.spawn_actor(sensor,carla.Transform(),attach_to=self.ego)
            self.collision.listen(self.on_collision)
            self.state.update(phase='live',profile=profile,scene_id='native-'+target.lower(),route_length_m=round(self.route.length),
                              lane_count=len(self.route.lane_offsets) if profile in ('yield','carpool') else 4,
                              physical_pedestrians=1 if profile in ('yield','carpool') else 0,error=None,mode='paused',speed_kph=0)
            self.navigation=NativeNavigation(self)
            from launch_native_carla import ensure_native_display
            ensure_native_display()

    def on_collision(self,event):
        if self.scenario:
            self.scenario.collision_count=getattr(self.scenario,'collision_count',0)+1
            impulse=event.normal_impulse.length()
            if self.profile=='cargo' and self.cargo and self.cargo.actor and event.other_actor.id==self.cargo.actor.id:
                self.scenario.impact_count+=1;self.scenario.impact_impulse=max(self.scenario.impact_impulse,impulse)
            self.scenario.log('collision',other_type=event.other_actor.type_id,other_id=event.other_actor.id,frame=event.frame,impulse_ns=impulse)

    def make_camera(self,quality):
        if quality not in SIZES:raise ValueError('Invalid camera quality')
        self.camera_generation+=1
        if self.rig:self.rig.close();self.rig=None;self.camera=None
        if self.camera:
            self.camera.stop();self.camera.destroy()
        generation=self.camera_generation
        def receive(img):
            if generation!=self.camera_generation:return
            try:self.images.get_nowait()
            except queue.Empty:pass
            try:self.images.put_nowait((generation,img))
            except queue.Full:pass
        from lab_settings import enabled,settings
        if enabled():
            from lab_capture import LabCapture
            cfg=settings();cfg['render']=list(SIZES[quality])
            if self.profile=='carpool':cfg['eye']=cfg['carpool_eye']
            self.rig=LabCapture(self.world,self.ego,cfg,receive);self.camera=self.rig.cameras['center']
            self.state.update(quality=quality,width=cfg['render'][0],height=cfg['render'][1],rig=dict(enabled=True,fov=cfg['fov'],yaw=cfg['yaw'],eye=cfg['eye'],render=cfg['render'],display=cfg['display'],sensor_count=3))
            return
        w,h=SIZES[quality];bp=self.world.get_blueprint_library().find('sensor.camera.rgb')
        if bp.has_attribute('role_name'):bp.set_attribute('role_name','hongik_native_single')
        for key,value in {'image_size_x':w,'image_size_y':h,'fov':55 if self.profile=='cargo' and self.scenario.zoom_requested else 100 if self.profile=='carpool' else 85,'sensor_tick':1/30,'motion_blur_intensity':0.}.items():
            if bp.has_attribute(key):bp.set_attribute(key,str(value))
        eye=carla.Location(x=.9,z=1.6)
        self.camera=self.world.spawn_actor(bp,carla.Transform(eye,carla.Rotation(pitch=-2,yaw=35 if self.profile=='carpool' else 0)),attach_to=self.ego)
        self.camera.listen(receive)
        self.state.update(quality=quality,width=w,height=h,camera=dict(eye=[.9,0.,1.6],yaw=35 if self.profile=='carpool' else 0,fov=100 if self.profile=='carpool' else 85))

    def control(self,body):
        with self.lock:
            if body.get('session_id') and (not self.scenario or body['session_id']!=self.scenario.session):
                raise ValueError('이전 주행 화면에서 온 요청입니다. 현재 내비를 새로 열어 주세요.')
            if body.get('reset'):
                if not self.profile:raise ValueError('시나리오를 먼저 선택해 주세요.')
                self.pending.put(('profile',self.profile))
            if 'mode' in body:
                if body['mode'] not in ('auto','paused'):raise ValueError('Invalid mode')
                if self.state['phase']!='live' or not self.scenario or self.scenario.completed:raise ValueError('시나리오를 먼저 준비해 주세요.')
                if body['mode']=='auto' and self.scenario.elapsed==0:
                    participant=self.research.current_participant()
                    if participant and getattr(self.scenario,'research_participant_id',None)!=participant['id']:
                        raise ValueError('참가자가 바뀌었어요. 시나리오를 다시 선택해 주세요.')
                    alignment=start_alignment(self.route,self.vehicles)
                    self.state['departure_alignment']=alignment
                    if not alignment['ready']:raise ValueError('차량의 출발 위치·방향이 달라졌습니다. 출발 위치로 다시 준비해 주세요.')
                self.command['mode']=body['mode']
                if body['mode']=='auto':self.research.start(self.scenario.session)
            if 'quality' in body:
                if body['quality'] not in SIZES:raise ValueError('Invalid quality')
                if self.ego is None:self.state['quality']=body['quality']
                else:self.pending.put(('quality',body['quality']))
        return {'accepted':True}

    def run(self):
        previous=None;last_trace=0.;last_weather=-1
        while not self.stop.is_set():
            try:
                try:
                    op,value=self.pending.get(timeout=.03 if self.world is None else .001)
                    if op=='profile':self.setup(value);previous=None;last_weather=-1
                    elif op=='quality':self.make_camera(value)
                except queue.Empty:pass
                if self.scenario is None:continue
                cycle_started=time.perf_counter()
                snapshot=self.world.wait_for_tick(2.)
                stamp=snapshot.timestamp.elapsed_seconds
                if previous is not None and stamp-previous<1/30:continue
                dt=0 if previous is None else min(.15,max(0,stamp-previous));previous=stamp
                with self.lock:
                    if self.state['phase']!='live':continue
                    sc=self.scenario;driving=self.command['mode']=='auto' and not sc.completed
                    self.state['mode']='auto' if driving else 'paused'
                    ego=self.vehicles[0];et=ego['actor'].get_transform()
                    ego['s'],_=self.route.project([et.location.x,et.location.y],ego['s']);self.ego_s=ego['s']
                    error=tracking_alignment(self.route,ego,et)['position_error_m']
                    if self.profile=='cargo':
                        self.update_cargo(dt,driving,snapshot,error)
                        continue
                    if self.profile=='yield':
                        self.update_yield(dt,driving,snapshot,error)
                        continue
                    if self.profile in CONTEXT_OPTIONS:
                        self.update_context(dt,driving,snapshot,error)
                        continue
                    for item in self.vehicles[1:]:
                        tr=item['actor'].get_transform()
                        item['s'],_=self.route.project([tr.location.x,tr.location.y],item['s'])
                    projected_at=time.perf_counter()
                    lead=self.vehicles[1];gap=max(0,lead['s']-ego['s']-lead['extent'].x-ego['extent'].x)
                    speed=self.ego.get_velocity().length()*3.6
                    sc.tick(dt,driving,speed,gap)
                    if getattr(sc,'study',None):sc.study.tick(dt,driving)
                    elapsed=sc.elapsed
                    fog=self.profile=='fog'
                    if fog and abs(fog_density(elapsed)-last_weather)>1:
                        weather=self.world.get_weather();weather.fog_density=fog_density(elapsed)
                        weather.fog_distance=0.;weather.fog_falloff=.1;self.world.set_weather(weather);last_weather=weather.fog_density
                    target=30.+(3.*math.sin(elapsed/5.5) if self.profile=='congestion' else 0.)
                    if fog:target=30.-15.*fog_density(elapsed)/99.
                    lead['speed']=target
                    lead_speed=lead['actor'].get_velocity().length()*3.6
                    ego['speed']=max(0,min(35.,lead_speed+(gap-sc.desired_gap)*1.8))
                    if sc.outcome.phase in ('stopping','complete') or elapsed>=300:ego['speed']=0.
                    ego['offset']=0.
                    if getattr(sc,'study',None):ego['speed'],ego['offset']=sc.study.targets(ego['speed'],ego['offset'])
                    if self.profile=='night':
                        u=min(1.,max(0.,(elapsed-10.)/5.));ramp=u*u*(3-2*u)
                        amplitude=.65*(.2 if elapsed<sc.settle_until else 1.)
                        lead['offset']=ramp*(1.6+amplitude*math.sin((elapsed-10.)*2*math.pi/10.5))
                    controls=[];traffic_alignment=[]
                    planned_at=time.perf_counter()
                    for j,item in enumerate(self.vehicles):
                        if item['role']=='truck':
                            preferred=[2.,20.,-14.][j-2]
                            item['speed']=max(25.,min(35.,30.+3*math.sin(elapsed/6+j)+.4*(ego['s']+preferred-item['s'])))
                        if item['role']=='fast':item['speed']=90.
                        if item['role']=='fast' and getattr(sc,'study',None) and sc.study.action=='merge' and sc.study.phase in ('applying','observing'):
                            sc.study.traffic_yield_ids.update(v['actor'].id for v in self.vehicles if v['role']=='fast' and v['s']<ego['s'])
                            item['speed']=20. if item['actor'].id in sc.study.traffic_yield_ids else 90.
                        if driving and item['role']=='fast' and item['s']-ego['s']>205:
                            # Recycle only beyond the front display range, behind the rear view.
                            rear=min(min(v['s'] for v in self.vehicles if v['role']=='fast')-23.,ego['s']-90.)
                            xyz,a=self.route.sample(rear,item['offset'])
                            item['actor'].set_transform(carla.Transform(carla.Location(x=float(xyz[0]),y=float(xyz[1]),z=float(xyz[2]+item['rest_z'])),carla.Rotation(yaw=math.degrees(a))))
                            recycled_speed=curve_speed_limit(self.route,rear,item['offset'],90.)/3.6
                            item['actor'].set_target_velocity(carla.Vector3D(x=recycled_speed*math.cos(a),y=recycled_speed*math.sin(a)))
                            item['actor'].set_target_angular_velocity(carla.Vector3D())
                            item['s']=rear;item['steer']=item['acc']=0.
                            controls.append(carla.command.ApplyVehicleControl(item['actor'].id,carla.VehicleControl()))
                            # The client transform cache still describes the old front position
                            # until the next snapshot. Never steer toward the rear from it.
                            continue
                        if item['role']=='fast':
                            # Different car models accelerate differently. Preserve the
                            # dense flow without allowing the faster model to rear-end it.
                            ahead=[v for v in self.vehicles if v is not item and v['role']=='fast' and 0.<v['s']-item['s']<70.]
                            if ahead:
                                front=min(ahead,key=lambda v:v['s'])
                                bumper=front['s']-item['s']-front['extent'].x-item['extent'].x
                                cap=front['actor'].get_velocity().length()*3.6+1.6*(bumper-14.)
                                item['speed']=max(0.,min(item['speed'],cap))
                        item['speed']=curve_speed_limit(self.route,item['s'],item['offset'],item['speed'])
                        actor=item['actor'];tr=actor.get_transform();v=actor.get_velocity().length()
                        traffic_alignment.append(tracking_alignment(self.route,item,tr))
                        steer=steering(self.route,item['s'],item['offset'],tr,v,item['geometry'])
                        item['steer']+=max(-dt*1.5,min(dt*1.5,steer-item['steer']))
                        difference=item['speed']/3.6-v
                        item['acc']=max(-3.,min(8.,item['acc']+difference*dt)) if driving else 0.
                        throttle=max(0,min(1.,.25+.3*difference+.08*item['acc'])) if difference>-.5 else 0.
                        brake=max(0,min(.8,-difference*.22)) if difference<-.5 else 0.
                        if item['speed']<.1:throttle,brake=0.,.7
                        if not driving:throttle,brake=0.,1.
                        controls.append(carla.command.ApplyVehicleControl(actor.id,carla.VehicleControl(
                            throttle=throttle,brake=brake,steer=item['steer'],hand_brake=not driving and v<.2)))
                    self.client.apply_batch(controls)
                    lights=carla.VehicleLightState.Position|carla.VehicleLightState.LowBeam
                    if sc.highbeam_on:lights|=carla.VehicleLightState.HighBeam
                    self.ego.set_light_state(carla.VehicleLightState(lights))
                    self.state.update(frame=snapshot.frame,speed_kph=round(speed,2),lane_error_m=round(error,3),
                                      profile=self.profile,physical_vehicles=len(self.vehicles),
                                      traffic_alignment=traffic_alignment,
                                      control_cycle_ms=round((time.perf_counter()-cycle_started)*1000,1),
                                      projection_ms=round((projected_at-cycle_started)*1000,1),
                                      planning_ms=round((planned_at-projected_at)*1000,1))
                    if elapsed-last_trace>=.5:
                        self.trace.write(json.dumps(dict(self.state,scenario=sc.public()),ensure_ascii=False)+'\n');last_trace=elapsed
                    if elapsed<last_trace:last_trace=elapsed
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self.state.update(phase='error',error=str(exc),mode='paused');self.command['mode']='paused'
                # Keep native actors braked on a controller error.
                for v in self.vehicles:
                    try:v['actor'].apply_control(carla.VehicleControl(brake=1,hand_brake=True))
                    except RuntimeError:pass
                if self.pedestrian:
                    try:self.pedestrian.actor.apply_control(carla.WalkerControl(speed=0.))
                    except RuntimeError:pass
                time.sleep(.5)
        self.clear_actors();self.trace.close()

    def update_cargo(self,dt,driving,snapshot,error):
        sc=self.scenario;ego=self.vehicles[0];truck=self.vehicles[1]
        tr=self.ego.get_transform();velocity=self.ego.get_velocity().length()
        tt=truck['actor'].get_transform()
        truck['s'],_=self.route.project([tt.location.x,tt.location.y],truck['s'])
        centre,yaw=self.route.sample(self.ego_s)
        offset=(tr.location.x-centre[0])*-math.sin(yaw)+(tr.location.y-centre[1])*math.cos(yaw)
        self.cargo.stage(truck['actor'],sc.elapsed)
        sc.truck_gap=truck['s']-self.ego_s-truck['extent'].x-ego['extent'].x
        if driving and not sc.onset and sc.elapsed>=sc.ONSET_SECONDS:
            self.cargo.release(truck['actor'],truck['s'],sc)
        distance,right,height=self.cargo.observation(self.ego_s)
        clear=left_lane_clear(self)
        sc.tick_cargo(dt,driving,velocity*3.6,distance,offset,clear,right,height)
        if getattr(sc,'study',None):sc.study.tick(dt,driving)
        if sc.zoom_requested and not sc.zoom_applied and velocity<.14:
            if not self.rig:self.make_camera(self.state['quality'])
            sc.zoom_applied=True
            sc.log('cargo_camera_zoom_applied',fov_deg=self.rig.config['fov'] if self.rig else 55,
                   inspection_fov_deg=55,mode='digital_inspection' if self.rig else 'camera_fov')
        target,lateral=sc.target()
        if getattr(sc,'study',None):target,lateral=sc.study.targets(target,lateral)
        if not sc.onset:target=following_speed(truck['actor'].get_velocity().length()*3.6,sc.truck_gap)
        controls=[]
        for item,kph,off in ((ego,target,lateral),(truck,25.,0.)):
            actor=item['actor'];at=actor.get_transform();v=actor.get_velocity().length()
            steer=steering(self.route,item['s'],off,at,v,item['geometry'])
            item['steer']+=max(-dt*1.2,min(dt*1.2,steer-item['steer']))
            difference=kph/3.6-v
            throttle=max(0.,min(.5,.18+.3*difference)) if difference>0 else 0.
            brake=max(0.,min(1.,-difference*.55)) if difference<0 else 0.
            if kph<.1 or not driving:throttle,brake=0.,1.
            controls.append(carla.command.ApplyVehicleControl(actor.id,carla.VehicleControl(
                throttle=throttle,brake=brake,steer=item['steer'],hand_brake=v<.12 and (not driving or kph<.1))))
        self.client.apply_batch(controls)
        if self.cargo.actor:
            # Physics pauses too; elapsed/event clocks never advance while paused.
            self.cargo.set_running(driving)
        self.state.update(frame=snapshot.frame,speed_kph=round(velocity*3.6,2),lane_error_m=round(error,3),
                          profile='cargo',physical_vehicles=2,physical_props=len(self.cargo.supports)+(1 if self.cargo.actor else 0),
                          physical_pedestrians=0,lateral_offset_m=round(offset,3),vehicle_target_kph=target)
        if snapshot.frame%15==0:self.trace.write(json.dumps(dict(self.state,scenario=sc.public()),ensure_ascii=False)+'\n')

    def update_yield(self,dt,driving,snapshot,error):
        sc=self.scenario;item=self.vehicles[0];actor=self.ego
        velocity=actor.get_velocity().length();speed=velocity*3.6
        sc.tick_yield(dt,driving,speed,self.ego_s,self.pedestrian.offset())
        if getattr(sc,'study',None):sc.study.tick(dt,driving)
        self.pedestrian.update(sc,driving)
        # Actual actor position gates release, independently of animation time.
        safe=self.pedestrian.cleared()
        target=sc.target_speed();lateral=0.
        if getattr(sc,'study',None):target,lateral=sc.study.targets(target,lateral)
        if sc.phase in ('resume','finishing','complete') and not safe:target=0.
        steer=steering(self.route,self.ego_s,lateral,actor.get_transform(),velocity,item['geometry'])
        item['steer']+=max(-dt*1.5,min(dt*1.5,steer-item['steer']))
        difference=target/3.6-velocity
        throttle=max(0,min(.45,.2+.28*difference)) if difference>0 else 0.
        brake=max(0,min(.8,-difference*.5)) if difference<0 else 0.
        if target<.1 or not driving:throttle,brake=0.,1.
        actor.apply_control(carla.VehicleControl(throttle=throttle,brake=brake,steer=item['steer'],hand_brake=velocity<.15 and (not driving or target<.1)))
        lights=carla.VehicleLightState.Position|carla.VehicleLightState.LowBeam
        if sc.public()['high_beam']['on']:lights|=carla.VehicleLightState.HighBeam
        actor.set_light_state(carla.VehicleLightState(lights))
        self.state.update(frame=snapshot.frame,speed_kph=round(speed,2),lane_error_m=round(error,3),
                          profile='yield',physical_vehicles=1,physical_pedestrians=1,
                          pedestrian_clear=safe,vehicle_target_kph=target)
        if snapshot.frame%15==0:self.trace.write(json.dumps(dict(self.state,scenario=sc.public()),ensure_ascii=False)+'\n')

    def update_context(self,dt,driving,snapshot,error):
        sc=self.scenario;item=self.vehicles[0];tr=self.ego.get_transform();velocity=self.ego.get_velocity().length()
        centre,yaw=self.route.sample(self.ego_s)
        offset=(tr.location.x-centre[0])*-math.sin(yaw)+(tr.location.y-centre[1])*math.cos(yaw)
        wp=self.road_map.get_waypoint(tr.location,project_to_road=False,lane_type=carla.LaneType.Any)
        safe=bool(wp and wp.lane_type in (carla.LaneType.Shoulder,carla.LaneType.Parking))
        clear=self.pedestrian.cleared(self.ego) if self.pedestrian else False
        sc.tick_context(dt,driving,velocity*3.6,self.ego_s,offset,clear,safe)
        if getattr(sc,'study',None):sc.study.tick(dt,driving)
        if self.pedestrian:self.pedestrian.update(sc,driving)
        target,lateral=sc.target()
        if getattr(sc,'study',None):target,lateral=sc.study.targets(target,lateral)
        steer=steering(self.route,self.ego_s,lateral,tr,velocity,item['geometry'])
        item['steer']+=max(-dt*1.2,min(dt*1.2,steer-item['steer']))
        difference=target/3.6-velocity
        throttle=max(0,min(.45,.2+.28*difference)) if difference>0 else 0.
        brake=max(0,min(.8,-difference*.45)) if difference<0 else 0.
        if target<.1 or not driving:throttle,brake=0.,1.
        self.ego.apply_control(carla.VehicleControl(throttle=throttle,brake=brake,steer=item['steer'],hand_brake=velocity<.15 and (not driving or target<.1)))
        self.state.update(frame=snapshot.frame,speed_kph=round(velocity*3.6,2),lane_error_m=round(error,3),
                          profile=self.profile,physical_vehicles=1,physical_pedestrians=1 if self.pedestrian else 0,
                          lateral_offset_m=round(offset,3),vehicle_target_kph=target)
        if snapshot.frame%15==0:self.trace.write(json.dumps(dict(self.state,scenario=sc.public()),ensure_ascii=False)+'\n')


def nav_js():
    js=(ROOT/'navigation.js').read_text(encoding='utf-8')
    js=js.replace("location.assign('http://127.0.0.1:8775/')","location.assign('/')")
    return js.encode('utf-8')


def native_navigation_html(midterm=False):
    html=navigation_html().decode('utf-8')
    # The small low-poly HMI need not compete with the CARLA road camera at 60Hz.
    html=html.replace('Math.min(devicePixelRatio,2)','Math.min(devicePixelRatio,1)')
    html=html.replace('function animate(now){requestAnimationFrame(animate);',
                      'function animate(now){requestAnimationFrame(animate);if(now-last<1000/24)return;')
    html=html.replace("item.kind==='pedestrian'?personMesh():carMesh", "item.kind==='obstacle'?new THREE.Mesh(new THREE.BoxGeometry(item.width_m,.45,item.length_m),new THREE.MeshStandardMaterial({color:0xa98450,roughness:1})):item.kind==='pedestrian'?personMesh():carMesh")
    if midterm:
        html=html.replace('src="/research-events.js','src="/midterm-panel.js')
        html=html.replace('</head>','<script defer src="/exterior-sound.js"></script><script defer src="/underbody-sound.js"></script><script defer src="/scene-audio.js"></script><script defer src="/midterm-audio.js"></script><link rel="stylesheet" href="/midterm-panel.css"></head>')
        html=html.replace('</head>','<script defer src="/feedback-voice.js"></script></head>')
    else:html=html.replace('</head>','<script defer src="/exterior-sound.js"></script><script defer src="/underbody-sound.js"></script><script defer src="/scene-audio.js"></script><script defer src="/city-study.js"></script><link rel="stylesheet" href="/city-study.css"></head>')
    return html.encode('utf-8')


def native_home_html():
    return (ROOT/'native_home.html').read_bytes().replace(b'<main>',b'<script src="/language.js"></script><script defer src="/participant-setup.js"></script><main>',1)


def handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def send(self,data,kind='application/json; charset=utf-8',code=200):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=urlparse(self.path).path
            try:
                if path=='/':self.send(native_home_html(),'text/html; charset=utf-8')
                elif path=='/admin':self.send((ROOT/'research_admin.html').read_bytes(),'text/html; charset=utf-8')
                elif path=='/admin/api/trials':self.send(bridge.research.list(parse_qs(urlparse(self.path).query).get('q',[''])[0]))
                elif path=='/admin/api/events':self.send(bridge.research.detail(parse_qs(urlparse(self.path).query).get('trial',[''])[0]))
                elif path=='/admin/export':self.send(bridge.research.export_csv(parse_qs(urlparse(self.path).query).get('kind',['trials'])[0]),'text/csv; charset=utf-8')
                elif path=='/api/participant/current':self.send(dict(participant=bridge.research.current_participant()))
                elif path=='/participant-setup.js':self.send((ROOT/'participant_setup.js').read_bytes(),'application/javascript')
                elif path=='/feedback-voice.js':self.send((ROOT/'feedback_voice.js').read_bytes(),'application/javascript')
                elif path=='/api/research-voice':
                    from research_voice import catalog
                    self.send(catalog(parse_qs(urlparse(self.path).query).get('lang',['ko'])[0]))
                elif path.startswith('/api/research-audio/'):
                    from research_voice import audio_path as response_audio
                    self.send(response_audio(path.removeprefix('/api/research-audio/').removesuffix('.wav')).read_bytes(),'audio/wav')
                elif path=='/api/language/zh':
                    from chinese_locale import catalog
                    self.send(catalog())
                elif path.startswith('/api/chinese-audio/'):
                    from research_voice import audio_path as chinese_audio,ALIASES
                    key=path.removeprefix('/api/chinese-audio/').removesuffix('.wav')
                    self.send(chinese_audio('zh_scene_'+ALIASES.get(key,key)).read_bytes(),'audio/wav')
                elif path=='/navigation':self.send(native_navigation_html(bridge.presentation=='midterm'),'text/html; charset=utf-8')
                elif path=='/navigation/classic':self.send(native_navigation_html(),'text/html; charset=utf-8')
                elif path in ('/midterm-panel.js','/midterm-panel.css'):
                    self.send((ROOT/('midterm_panel.js' if path.endswith('.js') else 'midterm_panel.css')).read_bytes(),'application/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
                elif path=='/midterm-audio.js':self.send((ROOT/'midterm_audio.js').read_bytes(),'application/javascript; charset=utf-8')
                elif path.startswith('/ui-assets/') and path.endswith('.svg'):
                    name=path.removeprefix('/ui-assets/')
                    if Path(name).name!=name:raise ValueError('Invalid asset')
                    self.send((ROOT/'ui_assets'/name).read_bytes(),'image/svg+xml')
                elif path=='/state':self.send(dict(bridge.state,scenario=bridge.scenario.public() if bridge.scenario else None))
                elif path=='/api/state':self.send(bridge.navigation.state())
                elif path=='/api/atlas':self.send(bridge.navigation.atlas())
                elif path=='/api/library':self.send({'tracks':music_library()})
                elif path.startswith('/media/'):stream_music(self,path.removeprefix('/media/'))
                elif path=='/api/reply':
                    q=parse_qs(urlparse(self.path).query);self.send(bridge.navigation.reply(q.get('session',[''])[0],q.get('id',[''])[0]))
                elif path.startswith('/api/narration/audio/'):
                    key=path.removeprefix('/api/narration/audio/').removesuffix('.wav')
                    self.send((city_audio_path(key) if key.startswith('city_') else pedestrian_audio_path(key) if key in ('yield','yield_notice') else audio_path(key)).read_bytes(),'audio/wav')
                elif path=='/nurec-nav.js':self.send(nav_js(),'application/javascript; charset=utf-8')
                elif path=='/pedestrian-ui.js':self.send((ROOT/'pedestrian_ui.js').read_bytes(),'application/javascript; charset=utf-8')
                elif path=='/city-study.css':self.send((ROOT/'city_study.css').read_bytes(),'text/css; charset=utf-8')
                elif path=='/city-study.js':self.send((ROOT/'city_study.js').read_bytes(),'application/javascript; charset=utf-8')
                elif path=='/exterior-sound.js':self.send((ROOT/'exterior_sound.js').read_bytes(),'application/javascript; charset=utf-8')
                elif path=='/underbody-sound.js':self.send((ROOT/'underbody_sound.js').read_bytes(),'application/javascript; charset=utf-8')
                elif path=='/research-events.js':
                    self.send((ROOT/'hongik_panel.js').read_bytes().replace(b'http://127.0.0.1:8775/',b'/').replace(b'|normal|complete)',b'|normal|complete|yield|city_yield|city_carpool|city_rattle)'),'application/javascript; charset=utf-8')
                elif path=='/drive':
                    self.send((ROOT/'drive.html').read_bytes().replace('NuRec'.encode(),b'CARLA RGB'),'text/html; charset=utf-8')
                elif path=='/frame.jpg':
                    if bridge.jpeg:
                        data=bridge.jpeg
                        if getattr(bridge,'rig',None) and bridge.profile=='cargo' and bridge.scenario.zoom_applied:
                            from lab_capture import inspection_jpeg
                            data=inspection_jpeg(data,bridge.rig.config['fov'])
                        self.send(data,'image/jpeg')
                    else:self.send_error(503)
                elif path=='/rig/bundle':
                    if not bridge.rig:self.send_error(409);return
                    params=parse_qs(urlparse(self.path).query);rig=bridge.rig
                    after=int(params.get('after',['-1'])[0]) if params.get('token',[''])[0]==rig.frames.token else -1
                    frame,data=rig.frames.after(after)
                    if data:self.send(data,'application/zip')
                    else:self.send(b'','application/zip',204)
                elif path=='/stream':
                    self.send_response(200);self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control','no-store');self.end_headers();last=-1
                    while not bridge.stop.is_set():
                        with bridge.frame_event:
                            bridge.frame_event.wait_for(lambda:bridge.frame_id!=last or bridge.stop.is_set(),3.)
                            data,last=bridge.jpeg,bridge.frame_id
                        if data:
                            self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data+b'\r\n');self.wfile.flush()
                else:
                    asset=static_asset(path)
                    if asset:self.send(asset[0],asset[1])
                    else:self.send_error(404)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
            except Exception as exc:self.send({'error':str(exc)},code=503)
        def do_POST(self):
            if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
                self.send_error(403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096:raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('Invalid request')
                if self.path=='/api/participant':
                    with bridge.lock:
                        if bridge.scenario and bridge.scenario.elapsed>0 and not bridge.scenario.completed:raise ValueError('현재 주행이 끝난 뒤 참가자를 변경해 주세요.')
                        participant=bridge.research.participant(body.get('name'))
                    self.send(dict(participant=participant))
                elif self.path=='/admin/api/sync':bridge.research.changed();self.send(dict(accepted=True))
                elif self.path=='/api/select':
                    profile=body.get('profile')
                    if profile not in PROFILES:raise ValueError('시나리오를 선택해 주세요.')
                    condition=body.get('condition','B');presentation=body.get('presentation','midterm')
                    if condition not in ('A','B') or presentation not in ('midterm','classic'):raise ValueError('Invalid presentation condition')
                    with bridge.lock:
                        if bridge.state['phase']=='preparing':raise ValueError('시나리오를 준비하고 있어요.')
                        bridge.condition=condition;bridge.presentation=presentation
                        bridge.language=body.get('language','ko') if body.get('language','ko') in ('ko','en','zh') else 'ko'
                        bridge.command['mode']='paused';bridge.state['phase']='preparing'
                        bridge.pending.put(('profile',profile))
                    self.send({'accepted':True})
                elif self.path=='/api/command':self.send(bridge.navigation.command(body))
                elif self.path=='/control':self.send(bridge.control(body))
                else:self.send_error(404)
            except (ValueError,TypeError,KeyError) as exc:self.send({'error':str(exc)},code=400)
        def do_HEAD(self):
            path=urlparse(self.path).path
            if path.startswith('/media/'):stream_music(self,path.removeprefix('/media/'),head=True)
            else:self.send_error(404)
    return Handler


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    class NativeHTTPServer(ThreadingHTTPServer):
        request_queue_size=64
    from lab_settings import enabled,settings
    quality=next(k for k,v in SIZES.items() if list(v)==settings()['render']) if enabled() else 'high'
    bridge=NativeBridge(quality);server=NativeHTTPServer(('127.0.0.1',PORT),handler(bridge))
    server.daemon_threads=True
    if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{PORT}/')
    print(f'CARLA native scenario app: http://127.0.0.1:{PORT}/',flush=True)
    try:server.serve_forever()
    finally:bridge.stop.set();bridge.research.close();server.server_close()


if __name__=='__main__':main()
