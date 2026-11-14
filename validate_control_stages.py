"""Owned-world staged physical checks. Results are local evidence, not public data."""
import argparse,json,math,time,urllib.request
from pathlib import Path
import carla
from native_carla_route import HighwayRoute,steering,curve_speed_limit
from native_alignment import steering_geometry
from vehicle_following import following_speed,imminent_contact,longitudinal
from launch_live import memory_state

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['solo','follow'],required=True);p.add_argument('--seconds',type=float,default=45.);p.add_argument('--speed',type=float,default=30.);p.add_argument('--offset',type=float,default=0.);a=p.parse_args()
 if memory_state()<2.:raise RuntimeError('Validation needs 2 GiB commit headroom')
 with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=3) as f:app=json.load(f)
 if app.get('phase')!='choose':raise RuntimeError('Leave app at scenario selection before isolated checks')
 client=carla.Client('127.0.0.1',2026);client.set_timeout(120);world=client.get_world()
 if world.get_settings().synchronous_mode:raise RuntimeError('Do not take over a synchronous world')
 if not world.get_map().name.endswith('/Town04'):world=client.load_world('Town04')
 print('Preparing mapped route',flush=True);route=HighwayRoute.build(world.get_map());print('Route ready',flush=True);owned=[];hits=[];rows=[]
 def spawn(bp,s):
  spec=world.get_blueprint_library().find(bp);spec.set_attribute('role_name','hongik_validation_'+a.stage)
  xyz,yaw=route.sample(s,a.offset);actor=world.spawn_actor(spec,carla.Transform(carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]+.45),carla.Rotation(yaw=math.degrees(yaw))))
  owned.append(actor);actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True));return {'actor':actor,'s':s,'command':0.,'steer':0.,'extent':actor.bounding_box.extent}
 try:
  ego=spawn('vehicle.tesla.model3',100.);cars=[ego]
  if a.stage=='follow':cars.append(spawn('vehicle.nissan.micra',111.3))
  sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=ego['actor']);owned.append(sensor);sensor.listen(lambda e:hits.append(e.other_actor.type_id))
  for _ in range(25):world.wait_for_tick(3)
  for item in cars:item['geometry']=steering_geometry(item['actor'])
  print('Driving check started: '+a.stage,flush=True);start=world.get_snapshot().timestamp.elapsed_seconds;previous=start;last_record=-1;deadline=time.monotonic()+a.seconds*2+30
  failure=None
  while time.monotonic()<deadline:
   snap=world.wait_for_tick(3);now=snap.timestamp.elapsed_seconds;dt=now-previous
   if dt<1/30:continue
   previous=now;t=now-start
   if dt>.5:failure='stale controller';break
   for item in cars:
    v=snap.find(item['actor'].id);tr=v.get_transform();item['s'],err=route.project((tr.location.x,tr.location.y),item['s']);point,_=route.sample(item['s'],a.offset);err=math.hypot(tr.location.x-point[0],tr.location.y-point[1]);item.update(transform=tr,speed=v.get_velocity().length(),error=err)
   gap=None;commands=[]
   for index,item in reversed(list(enumerate(cars))):
    target=curve_speed_limit(route,item['s'],a.offset,a.speed)/3.6;emergency=False
    if index==1 and 12<=t<19:target=0.
    if index==0 and len(cars)>1:
     leader=cars[1];gap=leader['s']-item['s']-leader['extent'].x-item['extent'].x
     target=following_speed(item['speed'],leader['speed'],gap,7.,target);emergency=imminent_contact(item['speed'],leader['speed'],gap)
    steer=steering(route,item['s'],a.offset,item['transform'],item['speed'],item['geometry']);item['steer']+=max(-dt*1.5,min(dt*1.5,steer-item['steer']))
    throttle,brake,item['command']=longitudinal(item['speed'],target,item['command'],dt,emergency)
    commands.append(carla.command.ApplyVehicleControl(item['actor'].id,carla.VehicleControl(throttle=throttle,brake=brake,steer=item['steer'])))
   client.apply_batch(commands)
   if t-last_record>=.2:
    rows.append({'t':round(t,3),'speed_kph':round(ego['speed']*3.6,2),'error_m':round(ego['error'],3),'gap_m':None if gap is None else round(gap,3),'dt':round(dt,4)});last_record=t
   if hits:failure='collision';break
   if ego['error']>1.:failure='lane departure';break
   if t>=a.seconds:break
  else:failure='wall timeout'
  result={'stage':a.stage,'requested_seconds':a.seconds,'elapsed':rows[-1]['t'] if rows else 0,'failure':failure,'collisions':hits,'max_error_m':max((r['error_m'] for r in rows),default=None),'min_gap_m':min((r['gap_m'] for r in rows if r['gap_m'] is not None),default=None),'rows':rows}
  out=Path(__file__).parent.parent/'lab-reports'/('control-stage-'+a.stage+'-'+str(int(a.speed))+'-'+str(a.offset)+'.json');out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
  if failure:raise RuntimeError(failure)
 finally:
  for actor in owned:
   try:
    if isinstance(actor,carla.Sensor):actor.stop()
    elif isinstance(actor,carla.Vehicle):actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
    actor.destroy()
   except RuntimeError:pass
if __name__=='__main__':main()
