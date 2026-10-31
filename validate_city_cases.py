"""Actual CARLA actor/command development checks for each city action."""
import argparse
import json
from pathlib import Path
import time
import urllib.request
import uuid
from launch_live import memory_state

BASE='http://127.0.0.1:8774'
def get(path):
 with urllib.request.urlopen(BASE+path,timeout=15) as r:return r.read()
def post(path,body):
 request=urllib.request.Request(BASE+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=15) as r:return json.load(r)
def run(profile,action):
 if memory_state()<2:raise RuntimeError('Validation needs 2 GiB commit headroom')
 folder=Path(__file__).resolve().parent/'validation'/('city-'+profile+'-'+action+'-'+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir()
 post('/api/select',{'profile':profile});deadline=time.monotonic()+120
 while time.monotonic()<deadline:
  s=json.loads(get('/state'))
  if s.get('error'):raise RuntimeError(s['error'])
  if s['phase']=='live' and s.get('profile')==profile and s['frames']>3:break
  time.sleep(.25)
 else:raise TimeoutError('Scene startup')
 sid=s['scenario']['session'];post('/control',{'mode':'auto'});sent=False;direct_done=False;last='';deadline=time.monotonic()+150;max_wait_speed=0;beam_seen=False
 def command(name,details=None):
  return post('/api/command',dict(session_id=sid,navigation_id=sid+'-weaving',request_id=uuid.uuid4().hex,action=name,client_event=details or {}))
 with (folder/'states.jsonl').open('w',encoding='utf-8') as log:
  while time.monotonic()<deadline:
   s=json.loads(get('/state'));sc=s['scenario']
   if s.get('error'):raise RuntimeError(s['error'])
   if sc['session']!=sid:raise RuntimeError('Trial changed during validation')
   if sc.get('collision_count',0):raise AssertionError('Vehicle collision was recorded')
   beam_seen=beam_seen or sc['high_beam']['on']
   phase=sc.get('yielding',sc.get('context'))['phase'];log.write(json.dumps(s,ensure_ascii=False)+'\n');log.flush()
   if phase!=last:
    last=phase;print(profile,action,phase,sc['elapsed_s'],s['speed_kph'],flush=True);(folder/(phase+'.jpg')).write_bytes(get('/frame.jpg'))
   if sc['onset'] and not sent and action!='none':
    command('study_open',{'options_visible':False});command('study_options',{'options_visible':True});command('study_choice',{'choice':action});command(action);sent=True
   if sc.get('direct_pending') and not direct_done and sc['elapsed_s']>=20:
    command('study_direct_done');direct_done=True
   if profile=='yield' and phase in ('mutual_wait','crossing','clearance'):
    max_wait_speed=max(max_wait_speed,s['speed_kph'])
    if s['speed_kph']>.6:raise AssertionError('Vehicle moved while waiting/crossing')
   if sc['completed']:
    if s['speed_kph']>=.5:raise AssertionError('End is not stationary')
    if action=='study_highbeam' and not beam_seen:raise AssertionError('High beam did not activate')
    if profile=='yield' and action=='study_horn' and sc['horn_count']!=1:raise AssertionError('Horn was not triggered once')
    result=dict(profile=profile,action=action,final=s,max_pedestrian_wait_speed=max_wait_speed,beam_seen=beam_seen,scope='Actual CARLA API and RGB, not browser/audio/participant study')
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(str(folder),flush=True);return
   time.sleep(.25)
 raise TimeoutError(str(folder))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('profile',choices=['yield','carpool','rattle']);p.add_argument('action');a=p.parse_args();run(a.profile,a.action)
