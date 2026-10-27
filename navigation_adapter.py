"""Serve the existing course navigation against this independent CARLA session.

Never imports the old display server, voice models, or port-2000 scenario runner.
"""
import json
import math
import mimetypes
import re
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from voice_bank import narration

ROOT = Path(__file__).resolve().parent
COURSE = Path.home()/'Desktop/홍익대/2026 2학기/휴먼 자율주행 인터렉션 디자인/CARLA-YOLO-실습'
WEB = ROOT/'course_ui' if (ROOT/'course_ui/index.html').is_file() else COURSE/'tesla-drive-ui'
OPTIONS = [
    dict(action='study_horn', label='클락션', detail='경적을 한 번 짧게 울리고 앞차의 반응을 살핍니다.'),
    dict(action='study_distance', label='차간 거리 넓히기', detail='서서히 감속해 앞차와의 간격을 넓힙니다.'),
    dict(action='study_wait', label='그냥 유지', detail='현재 주행 판단과 차간 거리를 유지합니다.')]
BLOCKADE_OPTIONS = [dict(action='study_highbeam',label='하이빔',detail='상향등을 두 번 켰다가 끄고 앞차의 반응을 살핍니다.'),*OPTIONS]
OVERTAKE_OPTION = dict(action='study_overtake', label='추월 시도', detail='왼쪽 차로로 이동해 앞차 추월을 시도합니다.')
FOG_OPTIONS = [
    dict(action='study_inspect',label='현재 안전조치 확인',detail='현재 속도와 앞차 간격, 감속 상태를 확인합니다.'),
    dict(action='study_distance',label='더 감속하고 거리 확보',detail='서서히 감속하며 앞차와의 간격을 더 넓힙니다.'),
    dict(action='study_stop_request',label='안전한 곳에 정차 요청',detail='정차 공간이 확인되지 않으면 우선 감속하며 주행합니다.')]


def navigation_html():
    html = (WEB / 'index.html').read_text(encoding='utf-8-sig')
    # Same HTML, Three.js, cockpit and research UI as 36; this route alone omits
    # providers which would start another session or claim unsupported inputs.
    html = re.sub(r'<script[^>]*src="/(?:qwen-speech|navigation-voice|hongik-wake|hongik-assistant|experience|multimodal)\.js[^>]*></script>', '', html)
    html = html.replace('<script src="/cockpit.js', '<script src="/nurec-nav-boot.js"></script><script src="/cockpit.js', 1)
    html = html.replace('<script type="module">', '<script src="/nurec-nav.js"></script><script type="module">', 1)
    html = html.replace('</head>', '<link rel="stylesheet" href="/nurec-nav.css"></head>')
    return html.encode('utf-8')


def static_asset(path):
    local = {'/nurec-nav.js': 'navigation.js', '/nurec-nav.css': 'navigation.css',
             '/research-events.js': 'hongik_panel.js',
             '/nurec-nav-boot.js': 'navigation_boot.js', '/drive': 'drive.html'}
    if path in local:
        file = ROOT / local[path]
    elif path in {'/cockpit.css', '/cockpit.js', '/research-events.css', '/research-events.js',
                  '/multimodal.css', '/hongik-assistant.css', '/vendor/three.module.js'}:
        file = WEB / path.lstrip('/')
    elif path.startswith('/vendor/') and path.endswith(('.js', '.woff2')):
        file = (WEB / path.lstrip('/')).resolve()
        if not file.is_relative_to((WEB / 'vendor').resolve()):
            return None
    else:
        return None
    if not file.is_file():
        return None
    data = file.read_bytes()
    return data, mimetypes.guess_type(str(file))[0] or 'application/octet-stream'


class NavigationAdapter:
    def __init__(self, bridge):
        self.bridge = bridge
        self.lock = threading.RLock()
        self.replies = {}
        self.requests = {}
        self.last_session = None
        self.options_open = False
        self.choice = None

    def options(self):
        sc=self.bridge.scenario
        if getattr(sc, 'OVERTAKE_TRIAL', False):
            reason=sc.overtake_unavailable_reason()
            return [*OPTIONS,dict(OVERTAKE_OPTION,disabled=bool(reason),disabled_reason=reason)]
        return BLOCKADE_OPTIONS if hasattr(sc,'high_beam') else FOG_OPTIONS if getattr(sc,'TYPE_ID',None)=='dense_fog' else OPTIONS

    def atlas(self):
        points = self.bridge.scene.route[:, :2, 3].copy()
        points[:, 1] *= -1  # CARLA left-handed XY, same as world_pose.
        width = 14.4 if self.bridge.scenario.public().get('layout') == 'four_lane_blockade' else 7.2
        return dict(map='NuRec measured route', roads=[dict(points=points.tolist(), width=width)], destinations=[])

    def state(self):
        b = self.bridge
        tr = b.ego.get_transform()
        yaw = math.radians(tr.rotation.yaw)
        cos, sin = math.cos(yaw), math.sin(yaw)
        def point(x, y, z=0, angle=0):
            dx, dy = x - tr.location.x, y - tr.location.y
            return dict(forward_m=round(dx*cos+dy*sin, 3), right_m=round(-dx*sin+dy*cos, 3),
                        up_m=round(z-tr.location.z, 3), yaw_deg=(angle-tr.rotation.yaw+180)%360-180)
        points = self.atlas()['roads'][0]['points']
        index = int(b.state.get('route_index', 0))
        route = b.scenario.route
        remaining = max(0, round(route.length - b.scenario.ego_s))
        lanes = []
        # Two-lane planning illustration around the measured trajectory, not a
        # claim that the source OpenDRIVE topology was fully imported.
        blockade=isinstance(getattr(b.scenario,'config',None),dict) and hasattr(b.scenario,'FAST_SPEED')
        lane_offsets=[(1,3.6),(2,0.),(3,-3.6),(4,-7.2)] if blockade else [(1,0.),(2,-3.6)]
        for lane, offset in lane_offsets:
            samples = []
            for distance in np.arange(b.scenario.ego_s-30, min(route.length, b.scenario.ego_s+130)+.01, 3.):
                matrix = route.sample(float(distance), offset, height=0.)
                if distance < 0:
                    matrix[:3, 3] += matrix[:3, 0] * distance
                x, y, z = matrix[:3, 3]
                angle = -math.degrees(math.atan2(matrix[1, 0], matrix[0, 0]))
                samples.append(dict(**point(x, -y, tr.location.z-.4, angle), width_m=3.6))
            if len(samples) < 2:
                samples = [dict(forward_m=f, right_m=-offset, up_m=-.4, yaw_deg=0, width_m=3.6) for f in (-15, 15)]
            lanes.append(dict(id=lane, points=samples))
        actors = []
        for track, actor, _, _ in b.track_actors:
            visible_tracks=set(b.scenario.traffic_poses()) if getattr(b.scenario,'OVERTAKE_TRIAL',False) else {b.scenario.TRACK_ID}
            if b.scenario.enabled and not blockade and getattr(b.scenario,'SUPPRESS_OTHER_TRAFFIC',True) and track not in visible_tracks:
                continue
            at = actor.get_transform()
            p = point(at.location.x, at.location.y, tr.location.z-.4, at.rotation.yaw)
            if at.location.z < tr.location.z-50 or abs(p['right_m']) > 25 or not -30 < p['forward_m'] < 150:
                continue
            size = actor.bounding_box.extent
            spec=next((v for v in b.scenario.traffic_specs() if v['track_id']==track),None) if blockade else None
            dimensions=b.scenario.config['vehicles'][track]['size'] if spec else [size.x*2,size.y*2,size.z*2]
            actors.append(dict(id=actor.id, kind='vehicle', label='앞차', **p,
                               length_m=dimensions[0], width_m=dimensions[1], height_m=dimensions[2], speed_kmh=spec['speed']*3.6 if spec else 10.8))
        sc = b.scenario.public()
        outcome = sc['outcome']
        resolving = outcome['phase'] != 'idle'
        outcome_end = sc['completed'] and sc['completion_reason'] == 'action_outcome'
        congestion = sc['id'] == 'congestion_long'
        fog = sc['id'] == 'dense_fog'
        daytime = congestion or fog
        active = sc['enabled'] and sc['onset']
        event = dict(active=active and not sc['completed'], pending=resolving, outcome=outcome,
            feedback=sc['feedback'], options=self.options(),
            title='앞차가 차선을 반복해서 벗어나고 있습니다' if active else '앞차의 움직임을 살피며 주행합니다',
            description='앞차가 좌우로 흔들리며 차선 경계에 접근하고 있습니다. 차량은 앞차와의 거리를 확인하며 따라갑니다.'
                if active else '필요할 때 주행 상태를 확인할 수 있습니다.')
        destination = dict(id='trial_end', name='야간 주행 체험', point=points[-1], distance_m=round(route.length), detail='촬영 구간 끝까지 주행')
        if daytime:
            event.update(title='앞 차량 흐름에 따라 서행하고 있습니다' if active else '주행 흐름을 살피며 출발합니다',
                         description='앞차의 출발과 정지가 반복되고 있습니다. 차간 거리를 유지하며 서행합니다.' if active else '앞차와 간격을 유지하며 경로를 따라 주행합니다.')
            destination.update(name='고속도로 서행 체험', detail='정체와 서행을 포함한 유한 구간 주행')
            end_s=route.length-10.-b.scenario.half_length-1.85-b.scenario.desired_gap
            end=route.sample(end_s)[:2,3]
            remaining=max(0,round(end_s-b.scenario.ego_s))
            if sc['completed'] and not outcome_end:
                remaining=0
            destination['point']=[float(end[0]),-float(end[1])]
        if fog:
            title=('전방에 짙은 안개가 있습니다' if sc['fog']['stage'] in ('thick','dense','whiteout') else '전방에 안개가 짙어지고 있습니다') if active else '주행 환경을 살피고 있습니다'
            description=f"현재 약 {b.state.get('speed_kph',0):g}km/h로 주행하고 있으며 앞차 간격은 약 {sc['gap_m']:g}m입니다. "
            description+='시야가 제한되는 구간에서 감속하며 주행합니다.' if active else '경로를 따라 앞차와의 간격을 유지합니다.'
            event.update(title=title,description=description)
            destination.update(name='안개 주행 체험',detail='30초 후 안개가 짙어지는 약 5분 주행')
        if sc['completed']:
            event.update(title='주행 체험을 마쳤습니다',description='구간 끝에 도착해 정지했습니다. 처음으로를 누르면 다시 체험할 수 있습니다.')
        if blockade:
            event.update(title='앞과 오른쪽은 느리고 왼쪽은 빠르게 흐르고 있습니다' if active else '4차로 도로를 따라 출발합니다')
            destination.update(name='4차로 저속 차량 체험',detail='왼쪽 90 · 앞차와 오른쪽 대형차 25~35km/h 변화')
        voice=narration('blockade' if blockade else 'fog' if fog else 'congestion' if congestion else 'night',event['active'],sc['completed'])
        if resolving:
            # Action-end is not destination arrival, and never plays the arrival WAV.
            copy={'applying':'요청이 차량에 반영되는 모습을 확인해 주세요.',
                  'observing':'주행 화면에서 선택한 행동에 따른 결과를 살펴보세요.',
                  'stopping':'결과를 확인했습니다. 체험을 마무리하고 있어요.',
                  'complete':outcome['message']}
            voice=dict(text=copy[outcome['phase']],speaker='Sohee',url=None,cached=False)
            event.update(title='선택한 행동의 결과를 확인하고 있어요', description=voice['text'])
            if outcome_end:
                event.update(title='체험이 종료되었습니다',description=outcome['message'])
                voice['text']=outcome['message']
            crash=sc.get('crash',{})
            if sc['action']=='overtake' and not outcome_end:
                title='추월을 시도하고 있습니다'
                if crash.get('phase') in ('primary_impact','secondary_impact','aftermath'):
                    title='충돌이 발생했습니다'
                if crash.get('phase')=='failed':title='주행 체험을 중지합니다'
                voice=dict(text=outcome['summary'] or sc['feedback'],speaker='Sohee',url=None,cached=False)
                event.update(title=title,description=voice['text'])
        event.update(description=voice['text'],narration=voice,
            live_detail=f"현재 속도 {b.state.get('speed_kph',0):g} km/h · 앞차 간격 약 {sc['gap_m']:g} m")
        return dict(connected=b.state['phase']=='live', schema=2, map='NuRec highway' if daytime else 'NuRec nighttime',
            source='CARLA actual actor positions; scripted scenario, not YOLO detection', frame=b.world.get_snapshot().frame,
            timestamp=time.time(), ego=dict(id=b.ego.id, role='nurec_live_ego', forward_m=0.,right_m=0.,up_m=-.4,yaw_deg=0.,
                speed_kmh=b.state.get('speed_kph',0), lane_index=2 if blockade else 1, lane_count=4 if blockade else 2, lane_id=-2 if blockade else -1),
            road=dict(id=99002 if daytime else 99001, lanes=lanes), lane_width_m=3.6, actors=actors, destinations=[],
            world_pose=dict(x=tr.location.x,y=tr.location.y,yaw=tr.rotation.yaw),
            route=dict(destination=destination,points=points,index=index,remaining_m=remaining,
                arrived=sc['completed'] and not outcome_end,off_route=False),
            session=dict(session_id=sc['session'],stage='running' if sc['elapsed_s']>0 or b.command['mode']=='auto' else 'ready',
                scenario=3 if fog else 1 if congestion else 2,navigation=dict(id=sc['session']+'-weaving',status='monitoring',map_label='안개 구간' if fog else '고속도로 서행' if congestion else '야간 주행',
                    title=event['title'],body=event['description'],research_event=event)), nurec=dict(b.state, scenario=sc))

    def command(self, body):
        b = self.bridge
        sc = b.scenario
        with self.lock, sc.lock:
            session = body.get('session_id')
            if session != sc.session or body.get('navigation_id') != sc.session+'-weaving':
                raise ValueError('주행이 변경됐습니다. 현재 화면에서 다시 선택해 주세요.')
            if self.last_session != session:
                self.replies.clear(); self.requests.clear()
                self.options_open = False; self.choice = None
                self.last_session = session
            request = body.get('request_id')
            if not isinstance(request, str) or not 1 <= len(request) <= 128:
                raise ValueError('요청 ID가 필요합니다.')
            if request in self.requests:
                previous = self.requests[request]
                if previous['action'] != body.get('action'):
                    raise ValueError('같은 요청 ID에 다른 동작을 보낼 수 없습니다.')
                return previous['queued']
            action = body.get('action')
            details = body.get('client_event') or {}
            if not isinstance(details, dict):
                raise ValueError('Invalid client event')
            if action in {option['action'] for option in self.options()}:
                sc.require_action_available()
                if sc.completed:
                    raise ValueError('체험이 끝났습니다. 처음으로 돌아간 뒤 다시 선택해 주세요.')
                if not self.options_open or self.choice != action:
                    raise ValueError('대응 방법을 선택한 뒤 실행해 주세요.')
                chosen=next(option for option in self.options() if option['action']==action)
                if chosen.get('disabled'):raise ValueError(chosen['disabled_reason'])
                sc.log('navigation_execution_confirmed', action=action, client_event=details)
                value = {'study_horn':'horn','study_distance':'widen','study_wait':'maintain',
                         'study_inspect':'inspect','study_stop_request':'stop_request','study_highbeam':'highbeam',
                         'study_overtake':'overtake'}[action]
                result = sc.interaction(value, session)
                message = result['feedback']
                self.options_open = False
                self.choice = None
            elif action == 'emergency_stop':
                with b.lock:
                    b.command['mode'] = 'paused'
                sc.log('navigation_pause_requested', source='emergency_stop')
                message = '주행을 일시정지했습니다.'
            elif action in ('study_presented','study_open','study_close','study_options','study_choice','study_cancel'):
                if action == 'study_presented':
                    sc.interaction('notification_exposed', session)
                elif action == 'study_open':
                    if sc.onset:
                        sc.interaction('open', session)
                    else:
                        sc.dialog_open = True; sc.detail_opened = time.monotonic()
                    # One click can expose explanation and all choices together.
                    # It still never selects or executes an action.
                    self.options_open = bool(details.get('options_visible') is True and sc.onset and not sc.completed and not sc.outcome.active)
                    self.choice = None
                    if self.options_open:
                        sc.log('navigation_options_exposed',client_event=details,measurement='UI exposure; not gaze')
                elif action == 'study_close':
                    if sc.onset:
                        sc.interaction('close', session)
                    else:
                        sc.dialog_open = False; sc.detail_opened = None
                    self.options_open = False; self.choice = None
                elif action == 'study_options':
                    sc.require_action_available()
                    if not sc.onset or not sc.dialog_open:
                        raise ValueError('주행 정보를 먼저 열어 주세요.')
                    self.options_open = True
                elif action == 'study_choice':
                    sc.require_action_available()
                    if not self.options_open or not sc.dialog_open or details.get('choice') not in {o['action'] for o in self.options()}:
                        raise ValueError('대응 방법을 먼저 열어 주세요.')
                    chosen=next(option for option in self.options() if option['action']==details['choice'])
                    if chosen.get('disabled'):raise ValueError(chosen['disabled_reason'])
                    self.choice = details['choice']
                elif action == 'study_cancel':
                    self.choice = None
                sc.log('navigation_'+action, client_event=details, measurement='UI exposure/click; not gaze')
                message = '확인했습니다.'
            else:
                raise ValueError('이 체험에서 사용할 수 없는 동작입니다.')
            command_id = uuid.uuid4().hex
            queued = dict(session_id=session,command_id=command_id)
            self.requests[request] = dict(action=action,queued=queued)
            self.replies[command_id] = dict(accepted=True,message=message,session_id=session,action=action)
            return queued

    def reply(self, session, command):
        with self.lock:
            if session != self.bridge.scenario.session:
                return dict(accepted=False,message='주행 세션이 변경됐습니다.')
            return self.replies.get(command, dict(accepted=False,message='확인할 요청이 없습니다.'))
