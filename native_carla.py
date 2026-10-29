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
from native_carla_route import HighwayRoute, steering, fog_density
from scenario2 import Scenario2
from voice_bank import narration, audio_path

ROOT = Path(__file__).resolve().parent
PORT, RPC = 8774, 2026
PROFILES = {'congestion': '4차로 정체', 'night': '야간 졸음운전 차량', 'fog': '짙은 안개'}
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


class NativeNavigation(NavigationAdapter):
    def options(self):
        from navigation_adapter import BLOCKADE_OPTIONS, OPTIONS, FOG_OPTIONS
        return BLOCKADE_OPTIONS if self.bridge.profile == 'congestion' else FOG_OPTIONS if self.bridge.profile == 'fog' else OPTIONS

    def atlas(self):
        r = self.bridge.route
        centre=[r.sample(float(s),r.width*.5)[0][:2].tolist() for s in r.arc[::3]]
        return dict(map='CARLA Town04', roads=[dict(points=centre, width=r.width*4)],
                    destinations=[], buildings=[], context_source=None)

    def state(self):
        b = self.bridge
        if b.ego is None or b.scenario is None:
            return dict(connected=False, reason=b.state.get('error') or 'CARLA 도로와 차량을 준비하고 있어요.')
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
            extent=item['actor'].bounding_box.extent
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
        if outcome['phase']!='idle':
            title='체험이 종료되었습니다' if sc['completed'] else '선택한 행동의 결과를 확인하고 있어요'
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
                    route=dict(destination=dict(id='trial_end',name=PROFILES[profile],point=route_points[-1],
                                                distance_m=round(b.route.length),detail='CARLA 순환 고속도로 · 약 5분'),
                               points=route_points,index=int(b.ego_s% b.route.length/6),remaining_m=round(remain*30/3.6),
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
        self.state=dict(kind='hongik-native-carla',phase='choose',renderer_backend='carla',error=None,
                        mode='paused',quality=quality,width=SIZES[quality][0],height=SIZES[quality][1],
                        speed_kph=0,frames=0,frame=0,target_fps=30,measured_fps=0)
        self.command={'mode':'paused'};self.profile=None;self.scenario=None;self.ego=None
        self.vehicles=[];self.camera=None;self.collision=None;self.world=None;self.route=None;self.ego_s=100.
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

    def connect(self):
        from launch_native_carla import OWNED, CARLA, process_command
        owned=json.loads(OWNED.read_text(encoding='utf-8-sig')) if OWNED.is_file() else {}
        command=process_command(owned.get('carla'))
        if str(CARLA/'CarlaUE4.exe').lower() not in command.lower() or '-carla-rpc-port=2026' not in command:
            raise RuntimeError('이 앱이 시작한 CARLA를 확인하지 못했습니다. 50번 실행 파일을 사용해 주세요.')
        client=carla.Client('127.0.0.1',RPC);client.set_timeout(90.)
        world=client.get_world()
        if not world.get_map().name.endswith('/Town04'):
            world=client.load_world('Town04')
        settings=world.get_settings()
        if settings.synchronous_mode:
            raise RuntimeError('The native CARLA world is owned by a synchronous client.')
        if settings.no_rendering_mode:
            settings.no_rendering_mode=False;world.apply_settings(settings)
        self.client=client;self.world=world;self.route=HighwayRoute.build(world.get_map())

    def clear_actors(self):
        self.camera_generation+=1
        for actor in [self.camera,self.collision,*[v['actor'] for v in self.vehicles]]:
            if actor is not None:
                try:
                    if isinstance(actor,carla.Sensor):actor.stop()
                    actor.destroy()
                except RuntimeError:pass
        self.camera=self.collision=self.ego=None;self.vehicles=[]
        if self.world:
            for actor in self.world.get_actors().filter('vehicle.*'):
                if actor.attributes.get('role_name','').startswith('hongik_native_'):
                    actor.destroy()
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
        item=dict(actor=actor,s=s,offset=offset,role=role,speed=speed,steer=0.,acc=0.)
        self.vehicles.append(item)
        actor.set_light_state(carla.VehicleLightState(carla.VehicleLightState.Position|carla.VehicleLightState.LowBeam))
        return item

    def setup(self, profile):
        with self.lock:
            self.state.update(phase='preparing',error=None,mode='paused');self.command['mode']='paused'
            if self.world is None:self.connect()
            self.clear_actors();self.profile=profile;self.ego_s=100.
            with self.frame_event:
                self.jpeg=None;self.frame_id=0;self.state['frames']=0
            self.scenario=NativeScenario(profile,self.run_dir/(uuid.uuid4().hex[:8]+'-events.jsonl'))
            self.spawn('vehicle.tesla.model3',100.,0.,'ego',color='35,85,190')
            self.ego=self.vehicles[0]['actor']
            lead=self.spawn('vehicle.nissan.micra',100+self.scenario.BASE_GAP+4.2,0.,'lead',color='220,223,226')
            if profile=='congestion':
                for s,offset in [(102.,self.route.width),(120.,2*self.route.width),(86.,2*self.route.width)]:
                    self.spawn('vehicle.carlamotors.european_hgv',s,offset,'truck',30)
                for i in range(14):
                    self.spawn('vehicle.audi.a2' if i%2 else 'vehicle.tesla.model3',-40+i*23.,-self.route.width,'fast',90,
                               color=['185,189,193','45,49,55','214,216,219'][i%3])
            weather=carla.WeatherParameters(cloudiness=15,precipitation=0,sun_altitude_angle=-8 if profile=='night' else 40,
                                           fog_density=0,fog_distance=0,fog_falloff=.1,wetness=0)
            self.world.set_weather(weather)
            # Let every suspension settle before showing the ready state.
            for v in self.vehicles:v['actor'].apply_control(carla.VehicleControl(brake=1,hand_brake=True))
            for _ in range(16):self.world.wait_for_tick(2.)
            self.make_camera(self.state['quality'])
            sensor=self.world.get_blueprint_library().find('sensor.other.collision')
            self.collision=self.world.spawn_actor(sensor,carla.Transform(),attach_to=self.ego)
            self.collision.listen(self.on_collision)
            self.state.update(phase='live',profile=profile,scene_id='native-town04',route_length_m=round(self.route.length),
                              lane_count=4,error=None,mode='paused',speed_kph=0)
            self.navigation=NativeNavigation(self)

    def on_collision(self,event):
        if self.scenario:self.scenario.log('collision',other_type=event.other_actor.type_id,frame=event.frame)

    def make_camera(self,quality):
        if quality not in SIZES:raise ValueError('Invalid camera quality')
        self.camera_generation+=1
        if self.camera:
            self.camera.stop();self.camera.destroy()
        w,h=SIZES[quality];bp=self.world.get_blueprint_library().find('sensor.camera.rgb')
        for key,value in {'image_size_x':w,'image_size_y':h,'fov':85,'sensor_tick':1/30,'motion_blur_intensity':0.}.items():
            if bp.has_attribute(key):bp.set_attribute(key,str(value))
        self.camera=self.world.spawn_actor(bp,carla.Transform(carla.Location(x=.9,z=1.6),carla.Rotation(pitch=-2)),attach_to=self.ego)
        generation=self.camera_generation
        def receive(img):
            if generation!=self.camera_generation:return
            try:self.images.get_nowait()
            except queue.Empty:pass
            try:self.images.put_nowait((generation,img))
            except queue.Full:pass
        self.camera.listen(receive)
        self.state.update(quality=quality,width=w,height=h)

    def control(self,body):
        with self.lock:
            if body.get('reset'):
                if not self.profile:raise ValueError('시나리오를 먼저 선택해 주세요.')
                self.pending.put(('profile',self.profile))
            if 'mode' in body:
                if body['mode'] not in ('auto','paused'):raise ValueError('Invalid mode')
                if not self.scenario or self.scenario.completed:raise ValueError('시나리오를 먼저 준비해 주세요.')
                self.command['mode']=body['mode']
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
                snapshot=self.world.wait_for_tick(2.)
                stamp=snapshot.timestamp.elapsed_seconds
                if previous is not None and stamp-previous<1/30:continue
                dt=0 if previous is None else min(.15,max(0,stamp-previous));previous=stamp
                with self.lock:
                    if self.state['phase']!='live':continue
                    sc=self.scenario;driving=self.command['mode']=='auto' and not sc.completed
                    self.state['mode']='auto' if driving else 'paused'
                    ego=self.vehicles[0];et=ego['actor'].get_transform()
                    ego['s'],error=self.route.project([et.location.x,et.location.y],ego['s']);self.ego_s=ego['s']
                    for item in self.vehicles[1:]:
                        tr=item['actor'].get_transform()
                        item['s'],_=self.route.project([tr.location.x,tr.location.y],item['s'])
                    lead=self.vehicles[1];gap=max(0,lead['s']-ego['s']-lead['actor'].bounding_box.extent.x-ego['actor'].bounding_box.extent.x)
                    speed=self.ego.get_velocity().length()*3.6
                    sc.tick(dt,driving,speed,gap)
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
                    if self.profile=='night':
                        u=min(1.,max(0.,(elapsed-10.)/5.));ramp=u*u*(3-2*u)
                        amplitude=.65*(.2 if elapsed<sc.settle_until else 1.)
                        lead['offset']=ramp*(1.6+amplitude*math.sin((elapsed-10.)*2*math.pi/10.5))
                    controls=[]
                    for j,item in enumerate(self.vehicles):
                        if item['role']=='truck':
                            preferred=[2.,20.,-14.][j-2]
                            item['speed']=max(25.,min(35.,30.+3*math.sin(elapsed/6+j)+.4*(ego['s']+preferred-item['s'])))
                        if item['role']=='fast' and item['s']-ego['s']>205:
                            # Recycle only beyond the front display range, behind the rear view.
                            rear=min(v['s'] for v in self.vehicles if v['role']=='fast')-23.
                            xyz,a=self.route.sample(rear,item['offset'])
                            item['actor'].set_transform(carla.Transform(carla.Location(x=float(xyz[0]),y=float(xyz[1]),z=float(xyz[2]+.35)),carla.Rotation(yaw=math.degrees(a))))
                            item['actor'].set_target_velocity(carla.Vector3D(x=25*math.cos(a),y=25*math.sin(a)))
                            item['s']=rear
                        actor=item['actor'];tr=actor.get_transform();v=actor.get_velocity().length()
                        steer=steering(self.route,item['s'],item['offset'],tr,v)
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
                                      profile=self.profile,physical_vehicles=len(self.vehicles))
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
                time.sleep(.5)
        self.clear_actors();self.trace.close()


def nav_js():
    js=(ROOT/'navigation.js').read_text(encoding='utf-8')
    js=js.replace("location.assign('http://127.0.0.1:8775/')","location.assign('/')")
    js=js.replace('실측 촬영 경로 · NuRec × CARLA','CARLA Town04 · 순환 고속도로')
    js=js.replace('실제 촬영 구간 끝까지','CARLA 순환 고속도로 · 약 5분')
    js=js.replace('촬영 구간 체험 완료','CARLA 체험 완료')
    js=js.replace("$('route-note').textContent='현재 주행 창과 같은 차량·상황에 연결되어 있습니다.';",
                  "$('route-note').textContent='CARLA RGB · 같은 차량·상황에 연결되어 있습니다.';")
    return js.encode('utf-8')


def native_navigation_html():
    html=navigation_html().decode('utf-8')
    # The small low-poly HMI need not compete with the CARLA road camera at 60Hz.
    html=html.replace('Math.min(devicePixelRatio,2)','Math.min(devicePixelRatio,1)')
    html=html.replace('function animate(now){requestAnimationFrame(animate);',
                      'function animate(now){requestAnimationFrame(animate);if(now-last<1000/24)return;')
    return html.encode('utf-8')


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
                if path=='/':self.send((ROOT/'native_home.html').read_bytes(),'text/html; charset=utf-8')
                elif path=='/navigation':self.send(native_navigation_html(),'text/html; charset=utf-8')
                elif path=='/state':self.send(dict(bridge.state,scenario=bridge.scenario.public() if bridge.scenario else None))
                elif path=='/api/state':self.send(bridge.navigation.state())
                elif path=='/api/atlas':self.send(bridge.navigation.atlas())
                elif path=='/api/library':self.send({'tracks':[]})
                elif path=='/api/reply':
                    q=parse_qs(urlparse(self.path).query);self.send(bridge.navigation.reply(q.get('session',[''])[0],q.get('id',[''])[0]))
                elif path.startswith('/api/narration/audio/'):
                    key=path.removeprefix('/api/narration/audio/').removesuffix('.wav')
                    self.send(audio_path(key).read_bytes(),'audio/wav')
                elif path=='/nurec-nav.js':self.send(nav_js(),'application/javascript; charset=utf-8')
                elif path=='/research-events.js':
                    self.send((ROOT/'hongik_panel.js').read_bytes().replace(b'http://127.0.0.1:8775/',b'/'),'application/javascript; charset=utf-8')
                elif path=='/drive':
                    self.send((ROOT/'drive.html').read_bytes().replace('NuRec'.encode(),b'CARLA RGB'),'text/html; charset=utf-8')
                elif path=='/frame.jpg':
                    if bridge.jpeg:self.send(bridge.jpeg,'image/jpeg')
                    else:self.send_error(503)
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
                if self.path=='/api/select':
                    profile=body.get('profile')
                    if profile not in PROFILES:raise ValueError('시나리오를 선택해 주세요.')
                    with bridge.lock:
                        if bridge.state['phase']=='preparing':raise ValueError('시나리오를 준비하고 있어요.')
                        bridge.command['mode']='paused';bridge.state['phase']='preparing'
                        bridge.pending.put(('profile',profile))
                    self.send({'accepted':True})
                elif self.path=='/api/command':self.send(bridge.navigation.command(body))
                elif self.path=='/control':self.send(bridge.control(body))
                else:self.send_error(404)
            except (ValueError,TypeError,KeyError) as exc:self.send({'error':str(exc)},code=400)
    return Handler


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    class NativeHTTPServer(ThreadingHTTPServer):
        request_queue_size=64
    bridge=NativeBridge();server=NativeHTTPServer(('127.0.0.1',PORT),handler(bridge))
    server.daemon_threads=True
    if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{PORT}/')
    print(f'CARLA native scenario app: http://127.0.0.1:{PORT}/',flush=True)
    try:server.serve_forever()
    finally:bridge.stop.set();server.server_close()


if __name__=='__main__':main()
