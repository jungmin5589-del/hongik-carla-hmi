"""Live CARLA experiment checks. Motion stays OFF; synthetic audio is not human STT validation."""
import argparse,base64,json,time,urllib.request,urllib.error
from pathlib import Path
from launch_live import memory_state
URL='http://127.0.0.1:8774'
def api(path,body=None,timeout=8):
 r=urllib.request.Request(URL+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=timeout) as f:return json.load(f)
def main():
 p=argparse.ArgumentParser();p.add_argument('--trial',type=int,default=4);p.add_argument('--seconds',type=float,default=45);p.add_argument('--request');p.add_argument('--audio',type=Path);a=p.parse_args()
 if memory_state()<2:raise RuntimeError('Validation needs 2 GiB commit headroom')
 s=api('/state')
 if (s.get('motion') or {}).get('enabled'):raise RuntimeError('Motion must be OFF')
 if s.get('mode')=='auto' and not (s.get('scenario') or {}).get('completed'):raise RuntimeError('Another drive is active')
 api('/api/participant/clear',{});api('/api/select',{'experiment_index':a.trial,'option_order':0});end=time.monotonic()+180
 while time.monotonic()<end:
  try:
   s=api('/state')
   if s.get('error'):raise RuntimeError(s['error'])
   if s.get('phase')=='live':break
  except TimeoutError:pass
  time.sleep(.5)
 else:raise RuntimeError('Scene preparation timeout')
 # Load navigation geometry and allow shader/camera warm-up while stationary.
 api('/api/state',timeout=30);api('/api/atlas',timeout=30)
 warm=time.monotonic()+30
 while time.monotonic()<warm:
  s=api('/state')
  if s.get('departure_ready') or ('departure_ready' not in s and s.get('frames',0)>=30 and s.get('control_cycle_ms',999)<400):break
  time.sleep(.5)
 time.sleep(3)
 print('READY',s['profile'],s['runtime_revision'],flush=True)
 api('/control',{'mode':'auto'});rows=[];sent=False;fail=None;start=time.monotonic();end=start+a.seconds*3+120
 try:
  while time.monotonic()<end:
   s=api('/state');sc=s.get('scenario',{});elapsed=sc.get('elapsed_s',0);study=sc.get('study',{})
   if s.get('error'):raise RuntimeError(s['error'])
   rows.append(dict(elapsed=elapsed,gap=sc.get('gap_m'),speed=s.get('speed_kph'),guard=s.get('drive_guard'),collisions=sc.get('collision_count'),study=study.get('phase'),status=sc.get('outcome',{}).get('status'),fps=s.get('measured_fps')))
   if s.get('drive_guard') or sc.get('collision_count'):raise RuntimeError('Physical guard or collision')
   nav=api('/api/state');e=nav['session']['navigation']['research_event'];protocol=nav.get('experiment',{})
   if a.trial in (1,3) and (e.get('active') or e.get('options') or nav.get('passive')):raise RuntimeError('OFF leaked AI UI')
   if not sent and elapsed>=12 and (a.request or a.audio):
    text=a.request
    if a.audio:
     result=api('/api/stt/transcribe',{'audio':base64.b64encode(a.audio.read_bytes()).decode(),'language':'ko'})
     while True:
      job=api('/api/stt/jobs/'+result['job'])
      if job['state']=='done':text=job['text'];print('SYNTHETIC STT',job,flush=True);break
      if job.get('error'):raise RuntimeError(job['error'])
      time.sleep(.2)
    body=dict(session_id=sc['session'],text=text,source='voice' if a.audio else 'text')
    proposal=api('/api/experiment/request',body);print('PROPOSAL',proposal,flush=True)
    if not proposal.get('supported'):raise RuntimeError('Request not mapped')
    print('EXECUTE',api('/api/experiment/request',dict(body,execute=True)).get('message'),flush=True);sent=True
   if sc.get('completed'):
    print('COMPLETED',sc.get('completion_reason'),sc.get('outcome'),flush=True);break
   if elapsed>=a.seconds:break
   time.sleep(.4)
  else:raise RuntimeError('Drive timed out')
 except Exception as error:fail=str(error);raise
 finally:
  try:api('/control',{'mode':'paused'})
  except Exception:pass
  folder=Path(__file__).resolve().parent.parent/'lab-reports';folder.mkdir(exist_ok=True)
  path=folder/('experiment-'+str(a.trial)+'-'+str(int(time.time()))+'.json');path.write_text(json.dumps(dict(failure=fail,synthetic_audio=bool(a.audio),rows=rows),ensure_ascii=False,indent=2),'utf-8')
  print('VALIDATION',len(rows),'samples',rows[-1] if rows else None,flush=True)
if __name__=='__main__':main()
