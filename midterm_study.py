"""Junho's midterm flow: passive state, invitation, requests, cancel, actual outcome.

All clocks advance with the owned CARLA scenario. No perception or remote-agent
claims are derived from this scripted passenger study controller.
"""
import math,time

from action_outcome import ActionOutcome


def option(key, label, detail):
    return dict(action='study_'+key,scenario_action='request_'+key,label=label,detail=detail)


OPTIONS = {
 'congestion':[
  option('horn','클락션','내비에서 빠앙 소리를 한 번 재생하고 바로 주행을 마쳐요.'),
  option('merge','1차로로 진입하기','오늘 실험에서는 요청을 기록하고 현재 차로에서 주행을 종료해요.'),
  option('end_ride','근처에서 내리기','안전하게 정차할 장소를 확인하고 이용을 마쳐요.')],
 'fog':[
  option('inspect','주변 인식 화면 보기','차량 주변의 위치와 차로 표시를 자세히 살펴봐요.'),
  option('slow','더 천천히 가기','속도를 더 낮추고 앞차와의 거리를 확보해요.'),
  option('safe_stop','갓길에 세우기','정차할 공간을 확인한 뒤 천천히 이동해요.')],
 'night':[
  option('horn','클락션','앞차에 경적을 한 번 짧게 울려요.'),
  option('widen','거리 더 넓히기','앞차와 간격을 크게 벌려요.'),
  option('pass','안전할 때 앞질러 가기','왼쪽에 안전한 틈이 확보되면 추월해요.'),
  option('safe_stop','갓길에서 잠시 기다리기','정차할 공간을 확인하고 위험 차량이 멀어지길 기다려요.')],
 'yield':[
  option('announce','보행자에게 먼저 건너라고 알리기','외부 스피커로 양보 의사를 전해요.'),
  option('creep','천천히 출발하기','보행자가 횡단 구간을 벗어났는지 확인한 뒤 출발해요.'),
  option('end_ride','여기서 내리기','주변의 안전한 정차 장소를 먼저 확인해요.')],
 'carpool':[
  option('support','관제 센터 연결','지원 연결을 요청하고 차량의 대기 상태를 확인해요.'),
  option('relocate','지금 바로 출발하기','주변 사람이 물러나면 다른 대기 위치로 이동해요.'),
  option('end_ride','안전한 곳으로 옮겨서 내리기','주변을 확인하고 이동해 정차한 뒤 이용을 마쳐요.')],
 'rattle':[
  option('inspect','차량 상태 자세히 보기','현재 속도와 주행 상태, 확인된 경고를 살펴봐요.'),
  option('slow','천천히 가면서 점검하기','저속으로 주행하며 상태를 확인해요.'),
  option('safe_stop','갓길에 세우고 점검하기','비어 있는 정차 공간을 확인한 뒤 이동해요.')],
 'cargo':[
  option('inspect','물체를 자세히 확인하기','정지 후 전방 화면을 확대해 살펴봐요.'),
  option('avoid','피해서 지나가기 요청','왼쪽에 공간이 있을 때 천천히 회피해요.'),
  option('stop','멈춰서 기다리기','물체 앞에서 간격을 두고 기다려요.'),
  option('delegate','차량 판단에 맡기기','정지 후 주변을 확인하고 회피를 진행해요.')]
}

COPY = {
 'congestion':('앞이 서행 차량으로 막혀 있어요','앞차와 오른쪽 대형차는 느리게 가고, 왼쪽 차로에는 빠른 차량이 이어지고 있어요.','앞차와 거리를 유지하고 왼쪽 차로의 진입 공간을 확인하고 있어요.'),
 'fog':('짙은 안개 때문에 천천히 가고 있어요','안개가 짙어져 전방 시야가 제한되고 있어요.','속도를 낮추고 앞차와의 간격을 유지하고 있어요.'),
 'night':('앞차가 차선을 넘나들고 있어요','앞 차량이 좌우로 흔들리며 차선 경계에 접근하고 있어요.','앞차의 움직임을 살피고 차로를 유지하며 따라가고 있어요.'),
 'yield':('보행자가 건너지 않고 서 있어요','횡단보도 옆 보행자가 손짓하며 앞뒤로 움직이고 있어요.','횡단 여부를 확인하며 완전히 멈춰 기다리고 있어요.'),
 'carpool':('차 밖에서 누군가 문 쪽으로 다가왔어요','동승자를 기다리는 중 한 사람이 다가와 창문을 두드리고 있어요.','문을 닫은 채 대기하고 주변 사람과 이동 공간을 확인하고 있어요.'),
 'rattle':('차 바깥에서 반복적인 소리가 들려요','주행 중 차체 바깥에서 긁히거나 떨리는 듯한 소리가 들려요.','현재 주행 상태를 확인하고 있어요. 소리의 원인은 아직 확인되지 않았어요.'),
 'cargo':('전방에 낙하물이 있어 감속하고 있어요','앞 트럭에서 떨어진 물체가 도로에 남아 있어요.','물체 앞에서 감속하고 통과할 공간을 확인하고 있어요.')
}


class StudyMixin:
    """Keep established actor choreography, while owning request/result clocks."""
    def __init__(self,*args,**kwargs):
        self.study=None
        super().__init__(*args,**kwargs)
        if not hasattr(self,'profile'):
            self.profile={'pedestrian_yield':'yield','fallen_cargo':'cargo'}[self.TYPE_ID]
        self.study=StudyRequests(self)

    def interaction(self,action,session):
        if action.startswith('request_'):
            return self.study.schedule(action[8:],session)
        return super().interaction(action,session)

    def require_action_available(self):
        if self.study and not self.study.dispatching and self.study.phase not in ('idle','complete'):
            raise ValueError('선택한 요청을 진행하고 있어요. 취소하거나 결과를 확인해 주세요.')
        return super().require_action_available()

    def public(self):
        data=super().public()
        if self.study:
            data['collision_count']=getattr(self,'collision_count',0)
            data['study']=self.study.public()
            if self.study.phase!='idle':
                data['outcome']=self.study.outcome()
                data['feedback']=self.study.feedback
        return data

    def apply_original(self,action,session):
        return super().interaction(action,session)


class StudyRequests:
    def __init__(self,scenario):
        self.sc=scenario;self.bridge=None;self.condition='B'
        self.phase='idle';self.action=None;self.pending_at=None;self.started_at=None
        self.feedback='';self.summary='';self.status=None;self.dispatching=False
        self.observed=0.;self.stopped=0.;self.cancelled=False;self.view_seen=False
        self.target_offset=0.;self.safe_bay=None;self.safe_checked=False
        self.lane_started=False;self.lane_clear=False;self.safe_stable=0.;self.offset=0.
        self.repeat_count=0;self.service_end=False;self.traffic_yield_ids=set()
        self.original_action=None;self.base_lateral=None;self.last_dt=.04;self.last_level=None
        self.finish_after_horn=False;self.horn_started_wall=None
        self.bay_start_s=0.;self.bay_blocked_s=0.;self.bay_waiting=False

    def bind(self,bridge,condition):
        self.bridge=bridge;self.condition=condition
        self.sc.log('midterm_condition_assigned',condition=condition,presentation='junho_midterm',ui_version='20261106')

    def schedule(self,action,session,fixed=False):
        sc=self.sc
        if session!=sc.session:raise ValueError('현재 주행에서 다시 요청해 주세요.')
        if self.phase not in ('idle','complete'):raise ValueError('요청을 진행 중이에요.')
        if sc.completed:raise ValueError('주행이 끝났어요. 출발 설정에서 다시 준비해 주세요.')
        if not fixed and (self.condition!='B' or not sc.onset or not sc.dialog_open):
            raise ValueError('현재 상황을 먼저 확인해 주세요.')
        allowed={o['scenario_action'][8:] for o in OPTIONS[sc.profile]}|{'maintain'}
        if fixed:allowed|={'support','safe_stop'}
        if action not in allowed:raise ValueError('이 상황에서 제공하는 요청을 선택해 주세요.')
        self.action=action;self.phase='queued';self.pending_at=sc.elapsed
        self.feedback='요청을 준비했어요. 3초 안에 취소할 수 있어요.'
        self.summary='';self.status=None;self.cancelled=False;self.view_seen=False
        self.safe_checked=False;self.safe_bay=None;self.lane_started=False;self.safe_stable=0.;self.stopped=0.;self.observed=0.
        immediate=sc.profile=='congestion' and action=='horn'
        sc.log('request_queued',action=action,countdown_s=0 if immediate else 3,condition=self.condition,fixed_button=fixed)
        if immediate:self._execute()
        return sc.public()

    def cancel(self):
        if self.phase=='queued':
            self.sc.log('request_cancelled_before_execution',action=self.action)
            self.phase='idle';self.action=None;self.pending_at=None;self.feedback='요청을 취소했어요.'
        elif self.phase in ('applying','observing'):
            self.sc.log('request_cancelled_after_execution',action=self.action)
            self.cancelled=True;self.phase='stopping';self.status='cancelled';self.summary='요청을 중단하고 차량이 정차했어요.';self.feedback='요청을 중단하고 차량을 정지하고 있어요.'
        return self.feedback

    def handle(self,action,details):
        if action=='study_horn_finished':
            if not self.finish_after_horn or self.action!='horn':raise ValueError('재생 중인 경적이 없습니다.')
            if not self.sc.completed:self.finish_horn()
            return self.feedback
        if action=='study_cancel_pending':return self.cancel()
        if action=='study_view_opened':
            self.view_seen=True;self.sc.log('requested_view_exposed',action=self.action,measurement='UI exposure; not gaze')
            return '화면을 표시했어요.'
        if action=='study_fixed_help':return self.schedule('support',self.sc.session,fixed=True)['feedback']
        if action=='study_fixed_stop':return self.schedule('safe_stop',self.sc.session,fixed=True)['feedback']
        if action=='study_repeat':
            if self.phase!='observing' or self.action not in ('horn','widen','lateral','inspect'):
                raise ValueError('현재 결과에서 반복할 수 있는 요청이 없어요.')
            action=self.action;self.sc.outcome=ActionOutcome();self.sc.action_complete=False
            self.phase='idle';self.repeat_count+=1;self.sc.log('request_repeat',action=action,count=self.repeat_count)
            return self.schedule(action,self.sc.session)['feedback']
        raise ValueError('지원하지 않는 요청입니다.')

    def _execute(self):
        sc=self.sc;action=self.action;profile=sc.profile
        self.phase='applying';self.started_at=sc.elapsed;self.original_action=action
        self.base_lateral=self.offset
        sc.action_complete=False;sc.last_action=action;sc.feedback='요청을 반영하고 있어요.'
        if profile=='congestion' and action=='merge':
            self.stop_in_lane=True;self.stop_offset=self.offset;self.phase='stopping';self.status='cancelled'
            self.summary='1차로 진입 요청을 기록하고 현재 차로에서 주행을 종료했어요.'
            self.feedback='현재 차로에서 감속하고 주행을 마치고 있어요.'
            sc.outcome.phase='stopping';sc.outcome.status=self.status;sc.feedback=self.feedback
            sc.log('request_ended_without_lane_change',action=action,status=self.status,reason='stop_in_current_lane')
            return
        self.dispatching=True
        try:
            native=profile in ('congestion','night','fog')
            original=(native and action in ('horn','widen','inspect','maintain')) or (profile=='cargo') or (profile=='rattle' and action in ('inspect','safe_stop','maintain')) or (profile=='carpool' and action in ('relocate','maintain'))
            # Original implementations validate their own action and update physical targets.
            if original:
                mapped='safe_stop' if profile=='rattle' and action=='safe_stop' else action
                sc.last_action=None;sc.apply_original(mapped,sc.session)
            else:
                sc.last_action=action;sc.outcome.begin(action)
                if hasattr(sc,'action_at'):sc.action_at=sc.elapsed
                if profile=='yield' and action=='announce':sc.announcement_count+=1
                if action=='widen':sc.desired_gap=max(sc.desired_gap+8.,sc.WIDE_GAP)
            sc.outcome.phase='managed'
        finally:self.dispatching=False
        if action=='lateral':self.target_offset=max(-.65,self.offset-.5)
        if action in ('merge','pass','avoid'):self.target_offset=-float(getattr(self.bridge.route,'width',3.5)) if self.bridge else -3.5
        if action in ('safe_stop','end_ride'):
            self.bay_start_s=self.bridge.ego_s if self.bridge else 0.;self.bay_blocked_s=0.;self.bay_waiting=False
            self.safe_bay=find_bay(self.bridge) if self.bridge else None
            self.safe_checked=True
            if profile=='carpool' and self.bridge:
                # Existing start location is a validated parking lane. Move within it.
                self.safe_bay=find_nearby_parking(self.bridge)
                sc.last_action='relocate';sc.actor_retreat=True
        self.feedback={
          'horn':'경적을 한 번 울렸어요. 앞차의 반응을 확인하고 있어요.',
          'widen':'서서히 감속해 앞차와의 간격을 넓히고 있어요.',
          'lateral':'차로 안에서 옆 트럭과의 간격을 넓히고 있어요.',
          'merge':'왼쪽 차로의 안전한 틈을 기다리고 있어요.',
          'pass':'왼쪽 차로를 확인하고 앞차를 지나갈 공간을 살피고 있어요.',
          'slow':'속도를 더 낮추고 주행 상태를 확인하고 있어요.',
          'inspect':'주변과 차량 상태를 자세히 표시하고 있어요.',
          'announce':'외부 스피커로 먼저 건너시라고 알렸어요. 정지한 채 반응을 확인해요.',
          'creep':'보행자가 횡단 구간을 벗어났는지 확인하고 있어요.',
          'support':'지원 요청을 접수했어요. 차량 상태를 확인하며 안내를 기다려요.',
          'relocate':'주변 사람이 물러나면 대기 위치를 옮겨요.',
          'safe_stop':'정차할 공간을 확인하고 감속하고 있어요.',
          'end_ride':'안전하게 정차할 장소를 확인하고 있어요.',
          'maintain':'현재 차량의 대응을 유지하고 있어요.',
          'avoid':'옆 차로를 확인하고 낙하물을 피할 공간을 살피고 있어요.',
          'stop':'낙하물 앞에서 간격을 두고 멈추고 있어요.',
          'delegate':'정지 후 주변 공간이 확보되면 회피해요.'}[action]
        sc.feedback=self.feedback;sc.log('request_execution_started',action=action,repeat_count=self.repeat_count)
        if profile=='congestion' and action=='horn':
            self.finish_after_horn=True;self.horn_started_wall=time.monotonic();self.horn_stop_offset=self.offset
            self.feedback='빠앙 소리를 재생하고 주행을 마치고 있어요.';sc.feedback=self.feedback

    def finish_horn(self,confirmed=True):
        sc=self.sc;self.phase='complete';self.status='achieved' if confirmed else 'unfulfilled'
        if self.bridge and hasattr(self.bridge,'command'):self.bridge.command['mode']='paused'
        self.summary='클락션을 한 번 울리고 주행을 종료했어요.' if confirmed else '경적 재생 완료를 확인하지 못해 주행을 종료했어요.'
        self.feedback=self.summary;sc.completed=True;sc.completion_reason='horn_audio_finished' if confirmed else 'horn_audio_timeout'
        sc.action_complete=confirmed;sc.feedback=self.summary;sc.outcome.phase='complete';sc.outcome.status=self.status;sc.outcome.summary=self.summary
        sc.log('request_completed',action='horn',status=self.status,reason=sc.completion_reason)

    def tick(self,dt,driving):
        sc=self.sc;b=self.bridge
        if self.finish_after_horn:
            if not sc.completed and time.monotonic()-self.horn_started_wall>10.:self.finish_horn(False)
            return
        self.last_dt=min(.15,max(0.,dt)) if driving else 0.
        elapsed=sc.elapsed-(getattr(sc,'onset_elapsed',None) or (10. if sc.profile in ('congestion','night','fog','cargo') else 0.))
        level=1 if elapsed<15. else 2 if elapsed<30. else 3
        if sc.onset and self.last_level!=level:
            self.last_level=level;sc.log('stimulus_level',level=level,condition=self.condition)
        if b and b.ego:
            loc=b.ego.get_location();centre,yaw=b.route.sample(b.ego_s)
            self.offset=float((loc.x-centre[0])*-math.sin(yaw)+(loc.y-centre[1])*math.cos(yaw))
        # A paused request cannot progress, but an already requested stop can
        # finish after the physical actor has actually remained stationary.
        if self.phase in ('idle','complete') or (not driving and (self.phase!='stopping' or not b or not b.ego)):return
        if self.phase=='queued':
            if sc.elapsed-self.pending_at>=3.:self._execute()
            return
        dt=min(.15,max(0.,dt));speed=b.ego.get_velocity().length()*3.6 if b and b.ego else 0.
        age=sc.elapsed-self.started_at if self.started_at is not None else 0.
        if self.phase=='applying':
            ready,status=self._ready(speed,age)
            timeout=120. if self.action in ('safe_stop','end_ride') and self.safe_bay else 50.
            if ready or age>=timeout:
                self.status=status if ready else 'unfulfilled';self.summary=self.describe()
                sc.action_complete=bool(ready and status=='achieved');sc.outcome.status=self.status;sc.outcome.summary=self.summary
                self.feedback=self.summary;self.phase='observing';self.observed=0.
                sc.log('request_result_observation',action=self.action,status=self.status,summary=self.summary)
        elif self.phase=='observing':
            self.observed+=dt
            if self.observed>=12.:
                self.phase='stopping';sc.outcome.phase='stopping'
                if hasattr(sc,'phase'):sc.phase='finishing'
        elif self.phase=='stopping':
            self.stopped=self.stopped+dt if speed<.5 else 0.
            if self.stopped>=1.:
                self.phase='complete';sc.completed=True;sc.completion_reason='request_stop' if getattr(self,'stop_in_lane',False) else 'action_outcome'
                sc.outcome.phase='complete';sc.outcome.summary=self.summary or self.feedback
                if hasattr(sc,'phase'):sc.phase='complete'
                self.service_end=self.action=='end_ride' and self.status=='achieved'
                sc.log('request_completed',action=self.action,status=self.status,service_end=self.service_end)

    def _ready(self,speed,age):
        sc=self.sc;b=self.bridge;a=self.action
        if getattr(sc,'collision_count',0):return speed<.5,'collision'
        if a=='horn':return age>=3.,'achieved'
        if a=='widen':return sc.gap>=sc.desired_gap-.8,'achieved'
        if a=='lateral':return abs(self.offset-self.target_offset)<.25 and age>=3.,'achieved'
        if a=='slow':return speed<=13. and age>=4.,'achieved'
        if a=='inspect':
            ready=self.view_seen and age>=3.
            if sc.profile=='cargo':ready=ready and sc.zoom_applied and speed<.5
            return ready,'achieved'
        if a in ('merge','pass'):
            adjacent=abs(self.offset-self.target_offset)<.8
            passed=b and (a=='merge' or b.ego_s>b.vehicles[1]['s']+9.)
            return adjacent and bool(passed) and age>4.,'achieved'
        if a in ('safe_stop','end_ride'):
            if not self.safe_bay:return speed<.5 and age>=5.,'partial'
            if self.bay_blocked_s>=10. and speed<.5:return True,'partial'
            import carla
            loc=b.ego.get_location();wp=b.world.get_map().get_waypoint(loc,project_to_road=False,lane_type=carla.LaneType.Any)
            parked=wp and wp.lane_type in (carla.LaneType.Shoulder,carla.LaneType.Parking)
            if parked and speed<.5:
                tr=b.ego.get_transform();yaw=math.radians(tr.rotation.yaw);extent=b.vehicles[0]['extent']
                for forward in (-extent.x,extent.x):
                    for right in (-extent.y,extent.y):
                        corner=carla.Location(x=loc.x+forward*math.cos(yaw)-right*math.sin(yaw),y=loc.y+forward*math.sin(yaw)+right*math.cos(yaw),z=loc.z)
                        cp=b.world.get_map().get_waypoint(corner,project_to_road=False,lane_type=carla.LaneType.Any)
                        if not cp or cp.lane_type not in (carla.LaneType.Shoulder,carla.LaneType.Parking):parked=False
            return bool(parked and abs(self.offset-self.safe_bay['offset'])<.65 and speed<.5),'achieved'
        if a in ('announce','creep'):
            clear=b and b.pedestrian and b.pedestrian.cleared()
            return bool(clear and sc.phase in ('resume','finishing','complete')),'achieved'
        if a=='relocate':return sc.relocation_done,'achieved'
        if a=='support':return age>=8.,'partial'
        if a in ('avoid','delegate'):return sc.verified_pass,'achieved'
        if a=='stop':return speed<.5 and age>4.,'achieved'
        return age>=8.,'achieved'

    def targets(self,speed,offset):
        if self.finish_after_horn:return 0.,self.horn_stop_offset
        if getattr(self,'stop_in_lane',False):return 0.,self.stop_offset
        if self.phase in ('idle','queued'):return speed,offset
        b=self.bridge;sc=self.sc;a=self.action
        if self.phase in ('stopping','complete') or self.status in ('unfulfilled','collision'):
            return 0.,self.offset
        if a in ('safe_stop','end_ride'):
            if not self.safe_bay:return 0.,self.offset
            if sc.profile=='carpool' and not sc.actor_clear:return 0.,self.offset
            if sc.profile=='yield' and b.pedestrian and not b.pedestrian.cleared():return 0.,self.offset
            ds=self.safe_bay['s']-b.ego_s
            if not path_to_bay_clear(b,self.safe_bay['offset']):
                self.bay_blocked_s+=self.last_dt
                if sc.profile in ('congestion','night','fog','rattle'):
                    self.bay_waiting=True
                    return min(speed,18. if sc.profile=='congestion' else 12.),self.offset
                return 0.,self.offset
            if self.bay_waiting:
                # Reserve a fresh run-in after adjacent trucks have passed.
                # The old stop point may already be beside or behind us.
                bay=find_bay(b)
                if not bay:return min(speed,18. if sc.profile=='congestion' else 12.),self.offset
                self.safe_bay=bay;self.bay_start_s=b.ego_s
                self.base_lateral=self.offset;self.bay_waiting=False
                ds=bay['s']-b.ego_s
            self.bay_blocked_s=0.
            runway=max(16.,self.safe_bay['s']-self.bay_start_s)
            u=min(1.,max(0.,(runway-ds)/max(4.,runway-12.)));u=u*u*(3.-2.*u)
            lateral=self.base_lateral+(self.safe_bay['offset']-self.base_lateral)*u
            # Never continue at the minimum crawl speed after passing the stop
            # point; actual full-vehicle parking containment gates success.
            if ds<=(.25 if sc.profile=='carpool' else 2.5):
                # A slow final alignment lets the rear corner clear the lane
                # boundary. Stop if alignment cannot be reached within 5 m.
                if abs(self.offset-self.safe_bay['offset'])>.10 and ds>-5.:return 1.5,lateral
                return 0.,lateral
            return max(3.,min(12.,max(0.,ds)*1.5)),lateral
        if a=='lateral':return speed,self.target_offset
        if a in ('merge','pass'):
            from fallen_cargo import left_lane_clear
            clear=left_lane_clear(b) and rear_approach_clear(b)
            if clear:self.safe_stable+=self.last_dt
            else:self.safe_stable=0.
            if self.safe_stable>=.5:self.lane_started=True
            if not self.lane_started:return speed,offset
            if not clear and abs(self.offset-self.target_offset)>.8:return 0.,self.offset
            return (40. if a=='pass' else 36.),self.target_offset
        if a=='slow':return min(12.,speed),offset
        if a=='support':return (0. if sc.profile in ('carpool','yield') else min(speed,12.)),offset
        return speed,offset

    def describe(self):
        a=self.action;sc=self.sc
        if self.status=='collision':return '접촉이 감지되어 차량을 정지했어요. 주변 상황을 확인하고 있어요.'
        if self.status=='unfulfilled':return '요청한 동작의 완료를 확인하지 못했어요. 차량을 정지하고 주변을 확인해요.'
        if a in ('safe_stop','end_ride'):
            if self.status=='partial':return '안전하게 옮겨 설 공간을 확인하지 못했어요. 현재 위치에서 정지 상태를 유지해요.'
            return '확인한 정차 공간으로 이동해 멈췄어요.'+(' 이용을 마칠 수 있어요.' if a=='end_ride' else ' 주변 상황을 확인하고 있어요.')
        return {
          'horn':'경적을 한 번 울렸어요. 앞차의 움직임을 살피며 주행했어요.',
          'widen':f'감속해 앞차와 약 {sc.desired_gap:g}m 간격을 확보했어요.',
          'lateral':'차로 안에서 옆 트럭과의 간격을 넓혔어요.',
          'merge':'왼쪽 차로의 공간을 확인하고 차로를 변경했어요.',
          'pass':'왼쪽 차로로 이동해 앞차를 지나갔어요.',
          'slow':'속도를 더 낮추고 주행 상태를 확인했어요.',
          'inspect':'주변 위치와 현재 차량 상태를 자세히 표시했어요. 확인되지 않은 원인은 계속 살피고 있어요.',
          'announce':'먼저 건너시라고 안내한 뒤 보행자가 횡단 구간을 벗어나는 것을 확인했어요.',
          'creep':'보행자가 횡단 구간을 벗어난 것을 확인한 뒤 서행으로 출발했어요.',
          'support':'지원 요청을 접수했어요. 실제 상담원 연결은 아직 확인되지 않아 현재 차량 상태를 유지해요.',
          'relocate':'주변 사람이 물러난 뒤 다른 대기 위치로 이동해 정차했어요.',
          'maintain':'추가 요청 없이 현재 차량의 대응을 유지했어요.',
          'avoid':'옆 차로로 이동해 낙하물을 지나갔어요.',
          'delegate':'정지 후 주변을 확인하고 낙하물을 피해 지나갔어요.',
          'stop':'낙하물 앞에서 간격을 두고 기다렸어요.'}.get(a,'차량의 대응 결과를 확인했어요.')

    def outcome(self):
        return dict(action=self.action,phase='applying' if self.phase=='queued' else self.phase,status=self.status,
                    summary=self.summary,observed_s=round(self.observed,2),observe_s=0. if self.finish_after_horn else 12.,
                    message=('주행이 끝났어요.' if self.finish_after_horn else '주변 상황을 확인했어요.') if self.phase=='complete' else self.feedback)

    def public(self):
        sc=self.sc
        elapsed=sc.elapsed-self.pending_at if self.pending_at is not None else 0.
        return dict(phase=self.phase,action=self.action,countdown_s=round(max(0.,3.-elapsed),2) if self.phase=='queued' else None,
                    condition=self.condition,cancellable=not self.finish_after_horn and self.phase in ('queued','applying','observing'),
                    repeatable=self.phase=='observing' and self.action in ('horn','widen','lateral','inspect'),
                    repeat_count=self.repeat_count,view_seen=self.view_seen,service_end=self.service_end,
                    safe_bay=self.safe_bay,offset_m=self.offset,request_elapsed_s=round(max(0.,sc.elapsed-(self.started_at or sc.elapsed)),2),
                    source='scripted passenger request and physical CARLA state; not live remote assistance')


def rear_approach_clear(b):
    """A distant fast vehicle can still close before a lane change finishes."""
    ego_speed=b.ego.get_velocity().length()
    for item in b.vehicles[1:]:
        actor=item['actor'];loc=actor.get_location()
        s,_=b.route.project([loc.x,loc.y],b.ego_s)
        centre,yaw=b.route.sample(s)
        offset=(loc.x-centre[0])*-math.sin(yaw)+(loc.y-centre[1])*math.cos(yaw)
        if abs(offset+b.route.width)>item['extent'].y+1.35:continue
        behind=b.ego_s-s;closing=(item.get('render_speed',0.)/3.6 if item.get('guided_flow') else actor.get_velocity().length())-ego_speed
        if 0.<behind<120. and closing>.5 and behind/closing<5.:return False
    return True


def find_nearby_parking(b):
    """Choose a full-footprint parking stop and check its final approach."""
    import carla
    sc=b.scenario;extent=b.vehicles[0]['extent'];road_map=b.world.get_map()
    for travel in (3.,4.,6.,9.,12.,15.,18.):
      if sc.start_s+travel+extent.x>=b.route.length:continue
      for shift in (0.,-.25,-.5,-.75,-1.):
        off=sc.base_offset+shift;valid=True
        for along in (travel-2.,travel,travel+.5):
          p,yaw=b.route.sample(sc.start_s+along,off)
          for forward in (-extent.x-.15,extent.x+.15):
            for right in (-extent.y-.12,extent.y+.12):
                q=carla.Location(x=float(p[0]+forward*math.cos(yaw)-right*math.sin(yaw)),y=float(p[1]+forward*math.sin(yaw)+right*math.cos(yaw)),z=float(p[2]))
                wp=road_map.get_waypoint(q,project_to_road=False,lane_type=carla.LaneType.Any)
                if not wp or wp.lane_type!=carla.LaneType.Parking:valid=False;break
            if not valid:break
          if not valid:break
        if valid:return dict(s=sc.start_s+travel,offset=off)
    return None


def bay_run_in_clear(route,start,base,stop,offset,obstacles):
    """Keep the full approach away from sign/light pole bases, not just the bay."""
    runway=max(16.,stop-start)
    for step in range(int(math.ceil(runway/2.))+4):
        distance=min(runway+5.,step*2.)
        u=min(1.,max(0.,distance/max(4.,runway-12.)));u=u*u*(3.-2.*u)
        p,_=route.sample(start+distance,base+(offset-base)*u)
        if any((p[0]-x)**2+(p[1]-y)**2<4.**2 for x,y in obstacles):return False
    return True


def find_bay(b):
    if not b or not b.route or not b.world:return None
    import carla
    small=b.profile in ('yield','carpool')
    offsets=(3.2,3.5,3.8) if small else (9.6,9.9,10.2,10.5)
    road_map=b.world.get_map()
    obstacles=[]
    for actor in b.world.get_actors():
        if actor.type_id.startswith(('traffic.traffic_light','traffic.stop','traffic.yield','static.prop.')):
            loc=actor.get_location();obstacles.append((loc.x,loc.y))
    base=getattr(getattr(b.scenario,'study',None),'offset',0.)
    # Crossing several lanes requires a real run-in; a nearby shoulder point
    # is not reachable by an immediate sideways shift.
    for ds in range(25 if small else 65,161,5):
        s=b.ego_s+ds
        if small and s>b.route.length-6.:break
        for off in offsets:
            valid=True
            for forward in (-4.,0.,4.):
                for lateral in (-1.5,1.5):
                    p,_=b.route.sample(s+forward,off+lateral)
                    wp=road_map.get_waypoint(carla.Location(x=float(p[0]),y=float(p[1]),z=float(p[2])),project_to_road=False,lane_type=carla.LaneType.Any)
                    if not wp or wp.lane_type not in (carla.LaneType.Shoulder,carla.LaneType.Parking):valid=False;break
                if not valid:break
            if valid and bay_run_in_clear(b.route,b.ego_s,base,s,off,obstacles):return dict(s=float(s),offset=float(off))
    return None


def path_to_bay_clear(b,offset):
    """Only the local lateral corridor; a route request never overrides occupancy."""
    ego=b.ego.get_transform();yaw=math.radians(ego.rotation.yaw)
    offset-=getattr(getattr(b.scenario,'study',None),'offset',0.)
    extents={v['actor'].id:v['extent'] for v in b.vehicles}
    for actor in b.world.get_actors():
        if actor.id==b.ego.id or not (actor.type_id.startswith('vehicle.') or actor.type_id.startswith('walker.')):continue
        loc=actor.get_location();dx,dy=loc.x-ego.location.x,loc.y-ego.location.y
        forward=dx*math.cos(yaw)+dy*math.sin(yaw);right=-dx*math.sin(yaw)+dy*math.cos(yaw)
        extent=extents.get(actor.id)
        if extent is None:extent=actor.bounding_box.extent
        if -7.-extent.x<forward<16.+extent.x and min(0.,offset)-1.4-extent.y<right<max(0.,offset)+1.4+extent.y:return False
    return True


def enrich_navigation(data,b):
    if not data.get('connected') or not getattr(b.scenario,'study',None):return data
    sc=b.scenario;study=sc.study;event=data['session']['navigation']['research_event']
    title,situation,behavior=COPY[sc.profile]
    if not sc.onset:
        title='동승자를 기다리고 있어요' if sc.profile=='carpool' else '경로를 따라 이동하고 있어요'
        situation='주변 교통과 주행 상태를 확인하고 있어요.'
    if sc.profile=='carpool' and sc.onset and sc.exterior.get('at_window'):title='차 밖에서 누군가 문을 두드리고 있어요'
    speed=b.state.get('speed_kph',0.)
    detail=f'현재 속도 {speed:.0f} km/h'
    if sc.profile in ('congestion','night','fog'):
        if study.action in ('merge','pass') and study.lane_started and abs(study.offset-study.target_offset)<.8:
            detail+=' · 왼쪽 차로 주행'
        else:detail+=f' · 앞차 간격 약 {sc.gap:.0f} m'
    elapsed=sc.elapsed-(getattr(sc,'onset_elapsed',None) or (10. if sc.profile in ('congestion','night','fog','cargo') else 0.))
    level=1 if elapsed<15. else 2 if elapsed<30. else 3
    event.update(title=title,situation=situation,vehicle_action=behavior,description=situation+' '+behavior,
                 active=sc.onset and not sc.completed and study.phase=='idle' and study.condition=='B',pending=study.phase not in ('idle','complete'),
                 feedback=study.feedback or sc.feedback,options=b.navigation.options(),staged_options=False,
                 hide_eta=True,live_detail=detail,condition=study.condition,level=level,study=study.public(),
                 outcome=study.outcome() if study.phase!='idle' else sc.outcome.public())
    if study.phase not in ('idle','queued'):
        event['description']=study.feedback;event['outcome']=study.outcome()
    data['session']['navigation'].update(title=title,body=event['description'])
    data['nurec']['scenario']=sc.public()
    if sc.profile in ('congestion','night','fog'):
        data['ego']['lane_index']=max(1,min(4,2+round(study.offset/b.route.width)))
    data['passive']=dict(title=title,body=behavior,detail=detail,door_locked=sc.profile=='carpool',
                         physical_state_source=True,level=level if sc.onset else 0)
    return data
