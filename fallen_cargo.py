"""One physical dropped box; scripted uncertainty, not a perception benchmark."""
import math
import threading
import time

import carla

from scenario2 import Scenario2
from city_voice import narration

OPTIONS = [
    dict(action='study_inspect', scenario_action='inspect', label='물체를 자세히 확인하기',
         detail='낙하물 앞에 정지하고 전방 화면을 확대해 살펴봅니다.'),
    dict(action='study_avoid', scenario_action='avoid', label='피해서 지나가기 요청',
         detail='왼쪽 차로가 비어 있는지 확인한 뒤 천천히 이동합니다. 공간이 없으면 정지합니다.'),
    dict(action='study_stop_request', scenario_action='stop', label='멈춰서 기다리기',
         detail='낙하물과 간격을 두고 정지한 채 기다립니다.'),
    dict(action='study_wait', scenario_action='delegate', label='차량 판단에 맡기기',
         detail='감속과 정지 후 주변 공간이 확보되면 차량이 회피를 진행합니다.')]


def cargo_stage(elapsed, rear_extent=3.97):
    """Continuous truck-local slide; no position reset at physical release."""
    u=min(1.,max(0.,(elapsed-8.8)/1.2))
    progress=u**1.35
    start=-2.7
    end=-rear_extent-.85
    pitch=16.*max(0.,(u-.68)/.32)**2
    return start+(end-start)*progress,pitch


def following_speed(truck_speed_kph, bumper_gap_m):
    return max(0.,min(25.,truck_speed_kph+(bumper_gap_m-12.)*1.15))


class CargoScenario(Scenario2):
    TYPE_ID = 'fallen_cargo'
    ONSET_SECONDS = 10.

    def __init__(self, event_path):
        self.lock = threading.RLock()
        self.events = open(event_path, 'a', encoding='utf-8', buffering=1)
        self.enabled = True
        self.reset()

    def reset(self, enabled=None):
        super().reset(enabled)
        self.phase = 'cruising'
        self.drop_s = None
        self.distance = None
        self.cargo_right = 0.
        self.cargo_height = None
        self.truck_gap = None
        self.fall_age = 0.
        self.action_at = None
        self.target_offset = 0.
        self.actual_offset = 0.
        self.left_clear = False
        self.collision_count = 0
        self.impact_count = 0
        self.impact_impulse = 0.
        self.verified_pass = False
        self.zoom_requested = False
        self.zoom_applied = False
        self.actor_id = None
        self.observed = self.stopped = 0.
        self.automatic = False
        self.delegate_stopped = False

    def release(self, actor_id):
        self.onset = True
        self.onset_monotonic = time.monotonic()
        self.drop_s = self.elapsed
        self.actor_id = actor_id
        self.phase = 'falling'
        self.log('cargo_released', actor_id=actor_id, stimulus='physical box; scripted uncertainty')

    def interaction(self, action, session):
        if action in ('notification_exposed', 'open', 'close'):
            return super().interaction(action, session)
        with self.lock:
            if session != self.session or not self.onset or not self.dialog_open:
                raise ValueError('현재 상황 설명을 먼저 열어 주세요.')
            self.require_action_available()
            if action not in {o['scenario_action'] for o in OPTIONS}:
                raise ValueError('이 상황의 선택지를 이용해 주세요.')
            self.last_action = action
            self.action_at = self.elapsed
            self.outcome.begin(action)
            self.zoom_requested = action == 'inspect'
            self.feedback = {
                'inspect': '낙하물 앞에 정지한 뒤 전방 화면을 확대합니다. 외관만으로 통과 안전성을 확정하지 않습니다.',
                'avoid': '주변 공간을 확인하고 있습니다. 왼쪽 공간이 비어 있을 때 천천히 회피합니다.',
                'stop': '낙하물과 간격을 두고 감속해 정지합니다.',
                'delegate': '우선 정지해 낙하물을 확인하고, 주변 공간이 확보되면 천천히 회피합니다.'}[action]
            self.log('action_applied', action=action)
            return self.public()

    def tick_cargo(self, dt, driving, speed, distance, offset, left_clear, right=0., height=None):
        with self.lock:
            self.distance, self.actual_offset, self.left_clear = distance, offset, left_clear
            self.cargo_right, self.cargo_height = right, height
            if not driving or self.completed:
                return
            dt = min(.15, max(0., dt))
            self.elapsed += dt
            if self.outcome.active:self.outcome.elapsed += dt
            if not self.onset:
                return
            self.fall_age = self.elapsed-self.drop_s
            if self.phase == 'falling' and self.fall_age > 2.5:
                self.phase = 'obstacle'
            if self.action_at is None and self.fall_age >= 65.:
                self.automatic = True
                self.last_action = 'stop'
                self.action_at = self.elapsed
                self.outcome.begin('stop')
                self.feedback = '별도 요청 없이 낙하물 앞에 정지한 상태를 유지합니다.'
                self.log('automatic_wait_started')
            if self.action_at is None:
                return
            age = self.elapsed-self.action_at
            wants_avoid = self.last_action in ('avoid', 'delegate')
            if self.last_action == 'delegate' and speed < .5:self.delegate_stopped = True
            # Start only after the cargo settles, while longitudinally separated.
            if (wants_avoid and self.fall_age > 3. and left_clear and
                    (self.last_action != 'delegate' or (age > 3. and self.delegate_stopped)) and distance is not None):
                self.target_offset = -3.5
                if distance < -7. and abs(offset+3.5) < .75:
                    self.verified_pass = True
            ready = (self.verified_pass if wants_avoid else
                     speed < .5 and age >= 4. and distance is not None and distance > 2.)
            if self.last_action == 'inspect':
                ready = ready and self.zoom_applied
            if self.impact_count:
                ready = speed < .5
            if self.outcome.phase == 'applying' and (ready or age >= 40.):
                self.action_complete = ready
                self.outcome.phase = 'observing'
                self.outcome.status = 'collision' if self.impact_count else 'achieved' if ready else 'unfulfilled'
                self.outcome.summary = self.summary()
                self.feedback = self.outcome.summary
                self.log('outcome_observation_started', action=self.last_action, status=self.outcome.status,
                         verified_pass=self.verified_pass, impact_count=self.impact_count)
            elif self.outcome.phase == 'observing':
                self.observed += dt
                self.outcome.observed = self.observed
                if self.observed >= 12.:
                    self.outcome.phase = 'stopping'
            elif self.outcome.phase == 'stopping':
                self.stopped = self.stopped+dt if speed < .5 else 0.
                if self.stopped >= 1.:
                    self.outcome.phase = 'complete'
                    self.completed = True
                    self.completion_reason = 'action_outcome'
                    self.phase = 'complete'
                    self.log('outcome_trial_completed', action=self.last_action, status=self.outcome.status)

    def target(self):
        if self.outcome.phase in ('stopping', 'complete') or self.outcome.status == 'unfulfilled' or self.collision_count or self.impact_count:
            return 0., self.actual_offset
        if not self.onset:
            return 25., 0.
        avoiding = self.target_offset < -1. and self.left_clear
        if avoiding:
            # Stop longitudinal advance until fully in the empty neighbouring lane.
            return (10. if abs(self.actual_offset+3.5) < .75 or (self.distance or 0.) > 13. else 3.), self.target_offset
        distance = self.distance
        return (max(0., min(16., ((distance or 0.)-8.)*1.1)) if distance is not None else 0.), (self.actual_offset if self.target_offset < -1. else 0.)

    def summary(self):
        if self.impact_count:
            return '낙하물과의 실제 접촉이 감지되어 차량을 정지했습니다. 주변 상황을 확인하고 있습니다.'
        if self.last_action in ('avoid', 'delegate'):
            return ('왼쪽의 비어 있는 차로로 이동해 낙하물을 지나갔습니다. 이동 결과를 확인했습니다.'
                    if self.verified_pass else '안전한 회피 완료를 확인하지 못해 차량을 정지합니다. 회피 완료로 기록하지 않습니다.')
        if self.last_action == 'inspect':
            return '정지 후 전방 화면을 확대해 낙하물을 살폈습니다. 화면만으로 재질이나 밟고 지나갈 때의 안전성을 확정하지 않았습니다.'
        return '낙하물 앞에서 간격을 두고 정지한 채 기다렸습니다. 낙하물은 도로에 남아 있습니다.'

    def public(self):
        with self.lock:
            return dict(id=self.TYPE_ID, session=self.session, enabled=True, onset=self.onset,
                        elapsed_s=round(self.elapsed, 2), duration_s=180, remaining_s=max(0,180-self.elapsed),
                        gap_m=round(self.distance or 0.,2), target_gap_m=8., horn_count=0,
                        high_beam=dict(on=False), dialog_open=self.dialog_open, action=self.last_action,
                        action_complete=self.action_complete, feedback=self.feedback, completed=self.completed,
                        completion_reason=self.completion_reason, outcome=self.outcome.public(), collision_count=self.collision_count,
                        cargo=dict(phase=self.phase, actor_id=self.actor_id, load_stage='falling' if self.onset and self.fall_age<2.5 else 'road' if self.onset else 'sliding' if self.elapsed>8.8 else 'loaded', distance_m=self.distance,
                                   fall_age_s=round(self.fall_age,2), offset_m=self.actual_offset, truck_gap_m=self.truck_gap,
                                   right_m=self.cargo_right, height_m=self.cargo_height, left_clear=self.left_clear,
                                   passed=self.verified_pass, impact_count=self.impact_count,
                                   impact_impulse_ns=self.impact_impulse, zoom=self.zoom_applied),
                        state_source='scripted ambiguous-object scenario; physical CARLA prop; not YOLO recognition')


class CargoActor:
    DECK_Z=1.34
    BOX='static.prop.box01'

    def __init__(self, world, route):
        self.world, self.route = world, route
        self.actor = None
        self.supports = []
        self.last_s = None
        self.running = False
        self.released = False
        self.saved_velocity = self.saved_angular = None

    def prepare(self, truck, s):
        # Two small rigid plates give the bare truck chassis a visible load support.
        # Supports remain rigidly attached; only the one carton is simulated.
        try:
            bp=self.world.get_blueprint_library().find('static.prop.ironplank')
            for x in (-2.20,-3.50):
                support=self.world.spawn_actor(bp,carla.Transform(carla.Location(z=15.)),
                                               attach_to=truck,attachment_type=carla.AttachmentType.Rigid)
                self.supports.append(support);support.set_collisions(False);support.set_simulate_physics(False)
                tr=truck.get_transform();support.set_transform(carla.Transform(tr.transform(carla.Location(x=x,z=self.DECK_Z-.025)),tr.rotation))
            bp=self.world.get_blueprint_library().find(self.BOX)
            pose=self.staged_pose(truck,0.)
            safe=carla.Transform(carla.Location(x=pose.location.x,y=pose.location.y,z=pose.location.z+15.))
            self.actor=self.world.try_spawn_actor(bp,safe)
            if self.actor is None:raise RuntimeError('트럭 적재 위치에 물체를 준비하지 못했습니다.')
            self.actor.set_collisions(False);self.actor.set_simulate_physics(False)
            self.actor.set_transform(pose)
            self.last_s=s-2.7
        except Exception:
            self.destroy();raise

    def staged_pose(self, truck, elapsed):
        tr=truck.get_transform()
        x,pitch=cargo_stage(elapsed,truck.bounding_box.extent.x)
        p=tr.transform(carla.Location(x=x,y=-.10,z=self.DECK_Z))
        return carla.Transform(p,carla.Rotation(yaw=tr.rotation.yaw,pitch=tr.rotation.pitch+pitch,roll=tr.rotation.roll))

    def stage(self, truck, elapsed):
        if self.actor and not self.released:
            self.actor.set_transform(self.staged_pose(truck,elapsed))

    def release(self, truck, s, sc):
        if not self.actor or self.released:raise RuntimeError('낙하물 적재 상태를 확인하지 못했습니다.')
        # The same visible carton reaches the edge before physics takes over.
        self.stage(truck,sc.ONSET_SECONDS)
        self.released=True;self.running=True
        self.actor.set_collisions(True)
        self.actor.set_simulate_physics(True)
        self.actor.set_enable_gravity(True)
        tr=truck.get_transform();velocity=truck.get_velocity();yaw=math.radians(tr.rotation.yaw)
        slide_speed=1.35*(truck.bounding_box.extent.x+.85-2.7)/1.2
        self.actor.set_target_velocity(carla.Vector3D(x=velocity.x-slide_speed*math.cos(yaw),
                                                     y=velocity.y-slide_speed*math.sin(yaw),z=velocity.z))
        # Mild edge tipping, not a large arbitrary spin.
        self.actor.set_target_angular_velocity(carla.Vector3D(x=-math.sin(yaw)*28.,y=math.cos(yaw)*28.,z=2.))
        sc.release(self.actor.id)

    def observation(self, ego_s):
        if not self.actor or not self.released:
            return None,0.,None
        loc=self.actor.get_location()
        self.last_s,_=self.route.project([loc.x,loc.y],self.last_s)
        p,yaw=self.route.sample(self.last_s)
        right=(loc.x-p[0])*-math.sin(yaw)+(loc.y-p[1])*math.cos(yaw)
        return self.last_s-ego_s-2.4,float(right),float(loc.z-p[2])

    def set_running(self, driving):
        if not self.actor or not self.released or self.running==driving:return
        if not driving:
            self.saved_velocity=self.actor.get_velocity();self.saved_angular=self.actor.get_angular_velocity()
        self.actor.set_simulate_physics(driving)
        if driving and self.saved_velocity is not None:
            self.actor.set_target_velocity(self.saved_velocity);self.actor.set_target_angular_velocity(self.saved_angular)
        self.running=driving

    def destroy(self):
        for actor in [self.actor,*self.supports]:
            if actor:
                try:actor.destroy()
                except RuntimeError:pass
        self.actor=None;self.supports=[]


def left_lane_clear(bridge):
    """Check current mapped lane and nearby physical vehicles, not elapsed time."""
    p,_ = bridge.route.sample(bridge.ego_s,-bridge.route.width)
    wp=bridge.world.get_map().get_waypoint(carla.Location(x=float(p[0]),y=float(p[1]),z=float(p[2])),
                                         project_to_road=False,lane_type=carla.LaneType.Driving)
    if wp is None or wp.is_junction:
        return False
    ego_wp=bridge.world.get_map().get_waypoint(bridge.ego.get_location())
    if ego_wp is None or wp.lane_id*ego_wp.lane_id<=0:
        return False
    for actor in bridge.world.get_actors().filter('vehicle.*'):
        if actor.id==bridge.ego.id:continue
        loc=actor.get_location()
        s,_=bridge.route.project([loc.x,loc.y],bridge.ego_s)
        if abs(s-bridge.ego_s)>35.:continue
        c,yaw=bridge.route.sample(s)
        off=(loc.x-c[0])*-math.sin(yaw)+(loc.y-c[1])*math.cos(yaw)
        if abs(off+bridge.route.width)<actor.bounding_box.extent.y+1.35:
            return False
    return True


def navigation_state(b, options):
    sc=b.scenario.public();tr=b.ego.get_transform();yaw=math.radians(tr.rotation.yaw)
    def local(x,y):
        dx,dy=x-tr.location.x,y-tr.location.y
        return dict(forward_m=dx*math.cos(yaw)+dy*math.sin(yaw),right_m=-dx*math.sin(yaw)+dy*math.cos(yaw),up_m=-.4,yaw_deg=0.)
    lanes=[]
    for i in range(4):
        points=[]
        for d in range(-20,100,3):
            p,_=b.route.sample(b.ego_s+d,(i-1)*b.route.width)
            points.append(dict(**local(p[0],p[1]),width_m=b.route.width))
        lanes.append(dict(id=i+1,points=points))
    actors=[]
    for item in b.vehicles[1:]:
        actor=item['actor'];at=actor.get_transform();e=actor.bounding_box.extent
        actors.append(dict(id=actor.id,kind='vehicle',role='lead',label='앞 트럭',vehicle_type='large',
                           length_m=e.x*2,width_m=e.y*2,height_m=e.z*2,speed_kmh=actor.get_velocity().length()*3.6,
                           world_pose=dict(x=at.location.x,y=at.location.y,yaw=at.rotation.yaw),**local(at.location.x,at.location.y)))
    if b.cargo.actor:
        actor=b.cargo.actor;at=actor.get_transform();e=actor.bounding_box.extent
        # Nav uses the existing generic obstacle symbol; camera retains the real mesh.
        actors.append(dict(id=actor.id,kind='obstacle',role='context',label='낙하물',length_m=max(.5,e.x*2),
                           width_m=max(.5,e.y*2),height_m=max(.3,e.z*2),speed_kmh=actor.get_velocity().length()*3.6,
                           world_pose=dict(x=at.location.x,y=at.location.y,yaw=at.rotation.yaw),**local(at.location.x,at.location.y)))
    voice=narration('city_cargo') if sc['onset'] else dict(text='앞 트럭과 간격을 유지하며 경로를 따라 주행합니다.',speaker='Sohee',cached=False,url=None)
    title='전방에 낙하물이 있어 감속하고 있어요' if sc['onset'] else '앞 트럭과 간격을 유지하고 있어요'
    pending=sc['outcome']['phase']!='idle'
    if pending:title='차량이 정차했습니다' if sc['completed'] else '요청한 대응을 진행하고 있어요'
    event=dict(active=sc['onset'] and not pending and not sc['completed'],pending=pending,outcome=sc['outcome'],
               title=title,description=sc['feedback'] if pending else voice['text'],narration=voice,feedback=sc['feedback'],
               options=options,staged_options=True,hide_eta=True,
               live_detail=f"현재 속도 {b.state['speed_kph']:.0f} km/h"+(f" · 낙하물까지 약 {max(0,sc['cargo']['distance_m']):.0f} m" if sc['cargo']['distance_m'] is not None else ''))
    points=b.route.points[::3,:2].tolist();sid=sc['session']
    return dict(connected=b.state['phase']=='live',schema=2,renderer='CARLA RGB',map='CARLA Town04',frame=b.state['frame'],timestamp=time.time(),
                source='physical dropped prop and scripted uncertainty; not perception inference',
                road=dict(id=4,lanes=lanes),lane_width_m=b.route.width,actors=actors,destinations=[],
                ego=dict(id=b.ego.id,role='native_carla_ego',forward_m=0,right_m=0,up_m=-.4,yaw_deg=0,
                         speed_kmh=b.state['speed_kph'],lane_index=2,lane_count=4,lane_id=-2),
                world_pose=dict(x=tr.location.x,y=tr.location.y,yaw=tr.rotation.yaw),
                route=dict(destination=dict(id='cargo_end',name='목적지',point=points[-1],distance_m=0,detail='경로 안내'),
                           points=points,index=0,remaining_m=0,arrived=False,off_route=False),
                session=dict(session_id=sid,stage='running' if sc['elapsed_s']>0 else 'ready',scenario=7,
                             navigation=dict(id=sid+'-weaving',status='monitoring',map_label='도로 위 낙하물',
                                             title=title,body=event['description'],research_event=event)),
                nurec=dict(b.state,scenario=sc))
