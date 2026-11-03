"""Capture a selected built-in walking cycle locally; generated poses never enter Git."""
import json,argparse
from pathlib import Path
import carla
import numpy as np
from launch_live import memory_state

CACHE=Path(__file__).resolve().parents[1]/'cache/exterior-gait/walker0034.json'

def frame(actor,names):
 bones={b.name:b for b in actor.get_bones().bone_transforms}
 return dict(loc=[[bones[n].relative.location.x,bones[n].relative.location.y,bones[n].relative.location.z] for n in names],
             rot=[np.asarray(bones[n].relative.get_matrix())[:3,:3].tolist() for n in names],
             comp=[np.asarray(bones[n].component.get_matrix())[:3,:3].tolist() for n in names])

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--model',choices=['walker.pedestrian.0034','walker.pedestrian.0001'],default='walker.pedestrian.0034');args=parser.parse_args()
 cache=CACHE if args.model.endswith('0034') else CACHE.with_name('walker0001.json')
 if memory_state()<2:raise RuntimeError('Gait preparation needs 2 GiB commit headroom')
 import urllib.request
 with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=5) as response:state=json.load(response)
 if state.get('kind')!='hongik-native-carla' or state.get('mode')!='paused':raise RuntimeError('Pause the owned CARLA-native app before gait capture')
 world=carla.Client('127.0.0.1',2026).get_world()
 ego=next((a for a in world.get_actors().filter('vehicle.*') if a.attributes.get('role_name')=='hongik_native_ego'),None)
 if ego is None:raise RuntimeError('Choose a CARLA-native pedestrian or carpool case and pause it first')
 t=ego.get_transform();f=t.get_forward_vector();r=t.get_right_vector();p=t.location+f*14-r*5
 bp=world.get_blueprint_library().find(args.model);bp.set_attribute('is_invincible','true');bp.set_attribute('role_name','exterior_gait_capture')
 actor=world.spawn_actor(bp,carla.Transform(p+carla.Location(z=.4),carla.Rotation(yaw=t.rotation.yaw)))
 camera=None
 try:
  bp=world.get_blueprint_library().find('sensor.camera.rgb')
  for key,value in {'image_size_x':160,'image_size_y':240,'fov':90,'sensor_tick':1/30}.items():bp.set_attribute(key,str(value))
  camera=world.spawn_actor(bp,carla.Transform(p+f*7+carla.Location(z=1.3),carla.Rotation(yaw=t.rotation.yaw+180)));camera.listen(lambda _:None)
  for _ in range(12):world.wait_for_tick(2.)
  names=sorted(b.name for b in actor.get_bones().bone_transforms);idle=frame(actor,names)
  actor.apply_control(carla.WalkerControl(direction=f,speed=.85))
  start=world.get_snapshot().timestamp.elapsed_seconds
  samples=[];times=[];speeds=[]
  while True:
   tick=world.wait_for_tick(2.);age=tick.timestamp.elapsed_seconds-start
   if age>.8:
    times.append(age);samples.append(frame(actor,names));speeds.append(actor.get_velocity().length())
   if age>4.8:break
  features=np.array([[np.asarray(s['rot'])[i].ravel() for i,n in enumerate(names) if any(k in n.lower() for k in ('thigh','leg','foot'))] for s in samples]).reshape(len(samples),-1)
  if features.shape[1]==0 or float(features.std(axis=0).max())<.03:raise RuntimeError('Native walking animation did not advance')
  dt=float(np.median(np.diff(times)))
  lags=list(range(max(2,int(.45/dt)),min(len(samples)//2,int(2.2/dt))))
  scores=[float(np.mean((features[:-lag]-features[lag:])**2)) for lag in lags]
  best=min(scores);lag=next(lag for lag,score in zip(lags,scores) if score<=best*1.15+1e-6)
  data=dict(model=args.model,source='local built-in CARLA walking cycle',names=names,idle=idle,
            frames=samples[:lag],period_s=lag*dt,reference_speed_mps=float(np.mean(speeds)),cycle_error=best)
  cache.parent.mkdir(parents=True,exist_ok=True)
  if cache.exists():
   import shutil,uuid
   shutil.copy2(cache,cache.with_suffix('.before-'+uuid.uuid4().hex+'.json'))
  temp=cache.with_suffix('.tmp.json');temp.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8');temp.replace(cache)
  print(json.dumps({'cache':str(cache),'bones':len(names),'frames':lag,'period_s':data['period_s'],'speed':data['reference_speed_mps'],'cycle_error':best}),flush=True)
 finally:
  if camera:
   camera.stop();camera.destroy()
  actor.destroy()

if __name__=='__main__':main()
