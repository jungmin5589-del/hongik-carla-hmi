"""Participant study orchestration; does not replace the physical controller."""
import re
TRIALS=[('practice','night',True),('s1_off','congestion',False),('s1_on','congestion',True),('s2_off','night',False),('s2_on','night',True)]
def spec(index,order=0):
 if type(index) is not int or not 0<=index<len(TRIALS):raise ValueError('Invalid trial index')
 key,profile,ai=TRIALS[index]
 return dict(index=index,trial_key=key,profile=profile,ai_enabled=ai,practice=key=='practice',option_order=int(order)%2)
def options(profile,order=0):
 from midterm_study import option
 rows=[option('notify','틈 생기면 알려 줘' if profile=='congestion' else '위험해지면 바로 알려 줘','상황 변화를 계속 확인해 알려드려요.'),option('widen','앞차랑 거리 좀 더 둬 줘' if profile=='congestion' else '거리 더 넓혀 줘','서서히 감속해 앞차와 간격을 확보해요.'),option('merge' if profile=='congestion' else 'pass','틈 나면 바로 1차로로 가 줘' if profile=='congestion' else '안전할 때 앞질러 가 줘','안전한 공간이 확보되면 이동해요.'),option('horn','경적 한 번 울려 줘','앞차에 경적을 한 번 울려요.')]
 return rows if not order else rows[2:]+rows[:2]
def intent(text,profile):
 t=re.sub(r'\s+','',str(text)).lower()
 if len(t)>1000:raise ValueError('요청은 1000자 이내로 입력해 주세요.')
 # Preserve unsupported route requests, rather than disguising them as a merge.
 if any(w in t for w in ('출구','다른길','돌아가','경로','exit','reroute')):return None
 if any(w in t for w in ('하지마','하지말','지말','지마','말고','취소','좁혀','가까이','donot',"don't",'不要','closer','缩短')):return None
 if any(w in t for w in ('왜','무슨상황','어떤상황','설명','why','explain','为什么','说明')):return 'explain'
 if any(w in t for w in ('알려','알림','notify','letmeknow','tellme','通知','提醒')):return 'notify'
 if any(w in t for w in ('거리','간격','떨어','distance','gap','车距','距离')) and any(w in t for w in ('넓','더','벌','확보','떨어','increase','more','拉大','扩大')):return 'widen'
 if any(w in t for w in ('경적','클락','클랙','빵','horn','鸣笛','喇叭')):return 'horn'
 passing=any(w in t for w in ('추월','앞질','overtake','超车')) or ('pass' in t and 'passenger' not in t)
 lane=any(w in t for w in ('1차로','일차로','왼쪽','leftlane','左侧车道')) and any(w in t for w in ('가줘','가줘요','가 줘','진입','이동','가자','가도','go','move','change','驶入'))
 if passing or lane:return 'merge' if profile=='congestion' else 'pass'
 if any(w in t for w in ('그냥','유지','기다릴','maintain','keepgoing','保持','等待')):return 'maintain'
 return None
class Protocol:
 def __init__(self,study,setting):
  self.study=study;self.setting=dict(setting);self.watch=False;self.notified=False;self.clear_s=0.;self.watch_at=None
  self.feedback='';self.last_request=None;self.temperature=21.;self.notice_id=0;self.request_serial=0;self.level=0
  self.sc.log('experiment_trial_assigned',**self.setting)
 def request(self,action):
  if action=='explain':
   from midterm_study import COPY
   title,situation,behavior=COPY[self.sc.profile]
   self.feedback=situation+' '+behavior;self.last_request='explain';self.request_serial+=1
   self.sc.log('experiment_explanation_only');return self.feedback
  if action=='maintain':
   self.stop_watch();self.last_request='maintain';self.feedback='현재 주행을 유지해요.';self.request_serial+=1
   self.sc.log('experiment_maintain');return self.feedback
  if action=='notify':
   self.watch=True;self.watch_at=self.sc.elapsed;self.notified=False;self.clear_s=0.
   self.watch_gap=self.sc.gap
   self.last_request='notify';self.feedback='상황 변화를 확인하고 알려드릴게요.';self.request_serial+=1
   self.sc.log('experiment_watch_started');return self.feedback
  return None
 def stop_watch(self):
  self.watch=False;self.notified=False;self.clear_s=0.
 @property
 def sc(self):return self.study.sc
 def tick(self,dt,driving):
  if not driving:return
  b=self.study.bridge
  if self.setting['practice']:
   if self.sc.elapsed>=120 and self.study.phase=='idle':
    self.study.action='practice_end';self.study.phase='stopping';self.study.status='achieved'
    self.study.summary=self.study.feedback='연습을 마치고 차량을 정차하고 있어요.'
    self.sc.log('experiment_practice_finishing')
   return
  if self.watch and not self.notified:
   from midterm_study import rear_approach_clear
   from fallen_cargo import left_lane_clear
   if self.sc.profile=='congestion':ready=left_lane_clear(b) and rear_approach_clear(b)
   else:
    lead=b.vehicles[1];gap=max(0.,lead['s']-b.ego_s-lead['extent'].x-b.vehicles[0]['extent'].x)
    ready=gap<max(3.,self.watch_gap-2.) or abs(lead['offset'])>2.
   self.clear_s=self.clear_s+dt if ready else 0.
   if self.clear_s>=1.5:
    self.notified=True;self.notify_at=self.sc.elapsed;self.notice_id+=1
    self.notice='왼쪽 차로에 진입할 여유가 확인됐어요. 이동하려면 대응을 선택해 주세요.' if self.sc.profile=='congestion' else '앞차의 움직임과 차간 거리에 주의가 필요해요. 대응을 선택할 수 있어요.'
    self.feedback=self.notice;self.sc.log('experiment_watch_notified',summary=self.notice)
  if self.watch and self.notified and self.sc.elapsed-self.notify_at>=20:
   self.watch=False;self.study.action='notify';self.study.status='achieved';self.study.summary=self.notice;self.study.feedback=self.notice;self.study.phase='stopping'
   self.study.observed=20.
 def enrich(self,data):
  if not data.get('connected'):return data
  data['experiment']=dict(self.setting,watching=self.watch,notified=self.notified,notice=getattr(self,'notice',''),notice_id=self.notice_id,
                          feedback=self.feedback,last_request=self.last_request,temperature=self.temperature,request_serial=self.request_serial)
  event=data['session']['navigation']['research_event']
  if not self.setting['ai_enabled'] or self.setting['practice']:
   event.update(active=False,options=[],description='',situation='',vehicle_action='',title='경로를 따라 주행',narration={},live_detail='',feedback='')
   data['session']['navigation'].update(title='경로를 따라 주행',body='')
   data['passive']={}
  else:
   from midterm_study import option
   event['options']=[*options(self.sc.profile,self.setting['option_order']),option('maintain','그냥 둘게요','현재 주행을 유지해요.')];event['experiment']=data['experiment']
   if self.notified:event.update(feedback=self.notice)
   elif self.feedback and self.study.phase=='idle':event['feedback']=self.feedback
  return data

def traffic_targets(profile,elapsed,practice=False,settled=False):
 """The same smooth stimulus timeline is used for OFF and ON."""
 def blend(a,b,start,end):
  u=min(1.,max(0.,(elapsed-start)/(end-start)));u=u*u*(3.-2.*u)
  return a+(b-a)*u
 if practice:return 30.,0.
 if profile=='congestion':
  speed=blend(35.,30.,10.,15.)-blend(0.,3.,25.,30.)-blend(0.,2.,40.,45.)
  return speed,0.
 amplitude=blend(.3,.5,25.,30.)+blend(0.,.15,40.,45.)
 ramp=blend(0.,1.,10.,15.)
 import math
 return 30.,ramp*(1.6+amplitude*(.2 if settled else 1.)*math.sin((elapsed-10.)*2*math.pi/10.5))
