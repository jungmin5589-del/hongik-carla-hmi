"""Anonymous, owned CARLA choice checks; physical evidence remains local."""
import argparse,json,time,uuid,urllib.request
from pathlib import Path
from launch_live import memory_state

def api(path,body=None):
 req=urllib.request.Request('http://127.0.0.1:8774'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)

def survey():
 try:p=api('/api/survey')
 except urllib.error.HTTPError as e:
  if e.code==400:return
  raise
 if p.get('recording'):raise RuntimeError('Participant trial left untouched')
 a={q['id']:('yes' if q['kind']=='notice' else 3) for q in p['schema']['questions'] if q.get('required')}
 api('/api/survey',dict(session_id=p['session_id'],answers=a,submit=True))

def run(profile,action,root):
 if memory_state()<2.:raise RuntimeError('Validation needs 2 GiB commit headroom')
 state=api('/state')
 if state.get('kind')!='hongik-native-carla' or state.get('motion',{}).get('enabled'):raise RuntimeError('Owned motion-OFF native app required')
 deadline=time.monotonic()+200
 while state.get('phase')=='preparing' and time.monotonic()<deadline:
  time.sleep(1.)
  try:state=api('/state')
  except TimeoutError:continue
 if state.get('phase')=='preparing':raise RuntimeError('Existing scene preparation timeout')
 if api('/api/participant/current').get('participant'):raise RuntimeError('Participant app left untouched')
 if state.get('scenario',{}):
  if state['scenario'].get('completed'):survey()
  elif state['scenario'].get('elapsed_s',0)>0:raise RuntimeError('Unfinished drive left untouched')
 api('/api/select',dict(experiment_index=2 if profile=='congestion' else 4,option_order=0,language='ko'))
 deadline=time.monotonic()+200
 while time.monotonic()<deadline:
  try:state=api('/state')
  except TimeoutError:
   print('Scene assets still loading',flush=True);continue
  if state.get('error'):raise RuntimeError(state['error'])
  if state.get('phase')=='live' and state.get('departure_ready'):break
  time.sleep(.5)
 else:raise RuntimeError('Departure readiness timeout')
 sid=state['scenario']['session'];folder=root/(profile+'-'+action+'-'+sid);folder.mkdir(parents=True)
 def command(name,details=None):
  r=api('/api/command',dict(session_id=sid,navigation_id=sid+'-weaving',request_id=uuid.uuid4().hex,action=name,client_event=details or {}))
  reply=api('/api/reply?session='+sid+'&id='+r['command_id'])
  if not reply.get('accepted'):raise RuntimeError(reply.get('message'))
 rows=[];sent=False;failure=None;captured=set();api('/control',dict(mode='auto',session_id=sid));start=time.monotonic();next_print=0
 try:
  while time.monotonic()-start<(360 if action=='baseline' else 280):
   state=api('/state');sc=state.get('scenario') or {};study=sc.get('study') or {};elapsed=sc.get('elapsed_s',0)
   if sc.get('session')!=sid:raise RuntimeError('Unexpected scenario replacement')
   rows.append(state)
   if state.get('error') or state.get('drive_guard') or sc.get('collision_count'):raise RuntimeError(state.get('error') or state.get('drive_guard') or 'collision')
   if elapsed>=next_print:
    if memory_state()<2.:raise RuntimeError('Validation needs 2 GiB commit headroom')
    print(profile,action,round(elapsed,1),state.get('speed_kph'),study.get('phase'),study.get('offset_m'),flush=True);next_print=elapsed+20
   if action!='baseline' and not sent and elapsed>=42.:
    command('study_open',{'options_visible':True});command('study_choice',{'choice':'study_'+action});command('study_'+action);sent=True
   stage=('drive-'+str(int(elapsed)//30*30)) if action=='baseline' else study.get('phase')
   if (action=='baseline' or stage in ('applying','observing','complete')) and stage not in captured:
    with urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg',timeout=5) as r:(folder/(stage+'.jpg')).write_bytes(r.read())
    captured.add(stage)
   if sc.get('completed'):break
   time.sleep(.4)
  else:raise RuntimeError('Physical run timeout')
  if action=='baseline':
   if sc.get('completion_reason')!='duration_end':raise RuntimeError('Baseline did not complete its full duration')
  elif sc.get('outcome',{}).get('status')!='achieved':raise RuntimeError('Action was not achieved')
 except Exception as e:failure=str(e)
 finally:
  if not sc.get('completed'):
   try:api('/control',dict(mode='paused',session_id=sid))
   except Exception as stop_error:failure=failure or str(stop_error)
  (folder/'samples.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
  result=dict(profile=profile,action=action,failure=failure,completed=sc.get('completed'),outcome=sc.get('outcome'),elapsed=sc.get('elapsed_s'),collisions=sc.get('collision_count'),samples=len(rows))
  (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
 if failure:raise RuntimeError(failure)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--cases',default='congestion:merge,night:pass');p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 for pair in a.cases.split(','):run(*pair.split(':'),a.output)
