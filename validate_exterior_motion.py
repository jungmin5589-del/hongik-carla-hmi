"""Actual CARLA movement/visual-gaze checks; optional RGB capture encoded after pausing."""
import argparse,json,math,time,urllib.request,uuid
from pathlib import Path
import carla
import numpy as np
from launch_live import memory_state
from timed_jpeg_capture import TimedJpegCapture

BASE='http://127.0.0.1:8774'
def get(path):
 with urllib.request.urlopen(BASE+path,timeout=10) as r:return json.load(r)
def post(path,data):
 with urllib.request.urlopen(urllib.request.Request(BASE+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'}),timeout=15) as r:return json.load(r)

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',action='store_true');args=p.parse_args()
 if memory_state()<2:raise RuntimeError('Validation needs 2 GiB commit headroom')
 if get('/state').get('kind')!='hongik-native-carla':raise RuntimeError('Expected native CARLA app')
 out=Path(__file__).resolve().parent/'validation'/('smooth-exterior-'+uuid.uuid4().hex);out.mkdir()
 post('/api/select',{'profile':'carpool'});deadline=time.monotonic()+100
 while time.monotonic()<deadline:
  s=get('/state')
  if s.get('error'):raise RuntimeError(s['error'])
  if s['phase']=='live' and s.get('profile')=='carpool' and s['frames']>3:break
  time.sleep(.2)
 else:raise TimeoutError('Carpool setup')
 world=carla.Client('127.0.0.1',2026).get_world()
 actor=next(a for a in world.get_actors().filter('walker.*') if a.attributes.get('role_name')=='hongik_native_exterior')
 sid=s['scenario']['session'];trace=[];states=[];last_state=0.;capture=None;captured=False;action_sent=False
 if args.video:capture=TimedJpegCapture(out);capture.start()
 post('/control',{'mode':'auto'});deadline=time.monotonic()+160
 try:
  while time.monotonic()<deadline:
   snap=world.wait_for_tick(2.);a=snap.find(actor.id)
   if not a:raise RuntimeError('Exterior actor disappeared')
   tr=a.get_transform();v=a.get_velocity();trace.append(dict(t=snap.timestamp.elapsed_seconds,x=tr.location.x,y=tr.location.y,yaw=tr.rotation.yaw,speed=math.hypot(v.x,v.y)))
   if time.monotonic()-last_state<.1:continue
   last_state=time.monotonic();s=get('/state');sc=s['scenario']
   if s.get('error') or sc['session']!=sid or sc['collision_count']:raise RuntimeError('Trial error/change/collision')
   states.append(s);ex=sc['context']['exterior']
   if capture and not captured and sc['elapsed_s']>=24:
    capture.stop();captured=True
   if ex.get('door_speech_started_s') is not None and sc['elapsed_s']-ex['door_speech_started_s']>=45 and not action_sent:
    def command(name,details=None):return post('/api/command',dict(session_id=sid,navigation_id=sid+'-weaving',request_id=uuid.uuid4().hex,action=name,client_event=details or {}))
    command('study_open',{'options_visible':False});command('study_options',{'options_visible':True});command('study_choice',{'choice':'study_external_notice'});command('study_external_notice');action_sent=True
   if sc['completed']:break
  else:raise TimeoutError('Motion trial did not finish')
 finally:
  (out/'states.json').write_text(json.dumps(states,ensure_ascii=False),encoding='utf-8');(out/'motion.json').write_text(json.dumps(trace),encoding='utf-8')
  current=get('/state')
  if not current.get('scenario',{}).get('completed'):post('/control',{'mode':'paused'})
  if capture and not captured:capture.stop()
 first_time=next(s['scenario']['elapsed_s'] for s in states if s['scenario']['context']['exterior'].get('dialogue_started_s') is not None)
 moving=[s['scenario']['context']['exterior'] for s in states if s['scenario']['context']['exterior'].get('phase')=='pacing' and s['scenario']['context']['exterior']['walk_speed_mps']>.08 and not s['scenario']['context']['actor_retreat']]
 if len(moving)<3:raise AssertionError('No moving-gaze samples')
 max_gaze=max(abs(x['gaze_error_deg']) for x in moving)
 if max_gaze>40:raise AssertionError('Visual gaze did not follow the vehicle: '+str(max_gaze))
 origin=trace[0]['t'];approach=[r for r in trace if 5.<r['t']-origin<10.]
 speeds=[math.hypot(b['x']-a['x'],b['y']-a['y'])/(b['t']-a['t']) for a,b in zip(approach,approach[1:]) if b['t']>a['t']]
 yaw=np.unwrap(np.radians([r['yaw'] for r in approach]));wobble=float(np.degrees(np.abs(np.diff(yaw)).sum()-abs(yaw[-1]-yaw[0])))
 if np.std(speeds)>.08 or wobble>5.:raise AssertionError('Native approach was not smooth: '+str((float(np.std(speeds)),wobble)))
 result=dict(passed=True,first_dialogue_s=first_time,moving_gaze_samples=len(moving),max_visual_gaze_error_deg=max_gaze,
             approach_mean_speed=float(np.mean(speeds)),approach_speed_std=float(np.std(speeds)),approach_excess_yaw_deg=wobble,
             final=s,scope='Actual CARLA kinematics and bone orientation; not subjective animation quality or physical speaker validation')
 if capture:
  result['capture_folder']=str(out)
  try:
   import imageio_ffmpeg
  except ImportError:result['video_note']='RGB JPEGs retained; encode in an environment with an installed video encoder'
  else:
   capture.encode(imageio_ffmpeg.get_ffmpeg_exe(),out/'approach-and-door.mp4');result['video']=str(out/'approach-and-door.mp4')
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True);print(out,flush=True)

if __name__=='__main__':main()
