"""Existing Hongiki navigation, with explicit NuRec capabilities and no crash option."""
import uuid
from navigation_adapter import NavigationAdapter,navigation_html

def navigation():
    html=navigation_html(city_audio=True).decode('utf-8')
    html=html.replace('src="/research-events.js','src="/midterm-panel.js')
    html=html.replace('</head>','<link rel="stylesheet" href="/midterm-panel.css"><script defer src="/feedback-voice.js"></script></head>')
    return html.encode('utf-8')

class NuRecNavigation(NavigationAdapter):
    def __init__(self,bridge):
        super().__init__(bridge);self.pending=None

    def options(self):
        return [dict(action='study_horn',scenario_action='horn',label='클락션',detail='경적을 한 번 울리고 주변 반응을 확인해요.'),
                dict(action='study_distance',scenario_action='widen',label='차간 거리 넓히기',detail='서서히 감속해 앞차와 간격을 넓혀요.'),
                dict(action='study_maintain',scenario_action='maintain',label='그냥 둘게요',detail='현재 차로와 차량의 대응을 유지해요.')]

    def state(self):
        result=super().state();sc=self.bridge.scenario;event=result['session']['navigation']['research_event']
        event.update(condition='B',staged_options=True,
            situation=('앞차와 오른쪽 대형차가 서행하고, 왼쪽에는 빠른 차량이 지나가요.' if self.bridge.args.profile=='congestion' else '앞차가 차선 경계 부근에서 좌우로 흔들리고 있어요.') if sc.onset else '주변 교통과 앞차의 움직임을 살피고 있어요.',
            vehicle_action='현재 차로를 유지하며 앞차와의 거리를 조절하고 있어요.',
            study=dict(phase=sc.outcome.phase,action=sc.last_action,status=sc.outcome.status,repeatable=False))
        if self.pending:
            event.update(pending=True,study=dict(phase='queued',action=self.pending['intent'],
                countdown_s=max(0.,self.pending['due']-sc.elapsed),repeatable=False,cancellable=True))
        result['nurec']['profile']=self.bridge.args.profile
        return result

    def command(self,body):
        sc=self.bridge.scenario;action=body.get('action')
        if action in {item['action'] for item in self.options()} or action=='study_cancel_pending':
            with self.lock,sc.lock:
                self.validate(body)
                key=body['request_id']
                if key in self.requests:
                    old=self.requests[key]
                    if old['action']!=action:raise ValueError('요청 ID가 중복됐어요.')
                    return old['queued']
                if action=='study_cancel_pending':
                    self.pending=None;message='요청을 취소했어요.'
                else:
                    if self.pending:raise ValueError('현재 요청을 먼저 확인해 주세요.')
                    sc.require_action_available()
                    if not self.options_open or self.choice!=action:raise ValueError('대응 방법을 선택한 뒤 실행해 주세요.')
                    intent={'study_horn':'horn','study_distance':'widen','study_maintain':'maintain'}[action]
                    from research_voice import intent_delay
                    language=(body.get('client_event') or {}).get('language','ko')
                    self.pending=dict(body=body.copy(),intent=intent,due=sc.elapsed+max(3.,intent_delay(intent,language)))
                    message={'horn':'경적을 한 번 울리고 주변 반응을 확인할게요.','widen':'서서히 감속해 앞차와 거리를 넓힐게요.','maintain':'현재 차로와 차량의 대응을 유지할게요.'}[intent]
                sc.log('navigation_'+action,client_event=body.get('client_event') or {},message=message)
                return self.ack(body,message)
        if action in ('study_fixed_help','study_fixed_stop'):
            with self.lock,sc.lock:
                self.validate(body)
                key=body.get('request_id')
                if not isinstance(key,str) or not 1<=len(key)<=128:raise ValueError('요청 ID가 필요해요.')
                if key in self.requests:
                    if self.requests[key]['action']!=action:raise ValueError('요청 ID가 중복됐어요.')
                    return self.requests[key]['queued']
                if action=='study_fixed_help':
                    text='지원 요청을 기록했어요. 실제 상담원 연결 기능은 아직 연결되지 않았어요.'
                else:
                    self.pending=None;sc.require_action_available();sc.last_action='stop_request';sc.action_complete=True
                    sc.feedback='갓길 공간이 확인되지 않아 현재 차로에서 서서히 감속해요.'
                    sc.outcome.begin('stop_request');sc.outcome.phase='stopping';sc.outcome.status='partial';sc.outcome.summary=sc.feedback
                    text=sc.feedback
                sc.log('navigation_'+action,client_event=body.get('client_event') or {})
                return self.ack(body,text)
        if action=='study_close' and body.get('session_id')==sc.session:self.pending=None
        return super().command(body)

    def validate(self,body):
        sc=self.bridge.scenario
        if body.get('session_id')!=sc.session or body.get('navigation_id')!=sc.session+'-weaving':raise ValueError('현재 주행에서 다시 요청해 주세요.')
        if not isinstance(body.get('client_event',{}),dict):raise ValueError('Invalid event')
        if self.last_session!=sc.session:
            self.pending=None;self.requests.clear();self.replies.clear();self.options_open=False;self.choice=None;self.last_session=sc.session
        key=body.get('request_id')
        if not isinstance(key,str) or not 1<=len(key)<=128:raise ValueError('요청 ID가 필요해요.')

    def ack(self,body,message):
        sc=self.bridge.scenario;cid=uuid.uuid4().hex;queued=dict(session_id=sc.session,command_id=cid)
        self.requests[body['request_id']]=dict(action=body['action'],queued=queued)
        self.replies[cid]=dict(accepted=True,message=message,session_id=sc.session,action=body['action'])
        return queued

    def tick(self):
        with self.lock,self.bridge.scenario.lock:
            sc=self.bridge.scenario;pending=self.pending
            if not pending:return
            if pending['body']['session_id']!=sc.session or sc.completed:
                self.pending=None;return
            if sc.elapsed<pending['due']:return
            self.pending=None
            body=dict(pending['body'],request_id=uuid.uuid4().hex)
            try:super().command(body)
            except ValueError as exc:
                sc.feedback=str(exc);sc.log('request_not_applied',reason=str(exc))
