"""Developer scene validation. Starts/resets owned scenes; never run during a participant drive."""
import argparse,json,math,time,urllib.request
from pathlib import Path
import numpy as np
import carla

ROOT=Path(__file__).resolve().parent;BASE='http://127.0.0.1:8774'

def get(path):
 with urllib.request.urlopen(BASE+path,timeout=15) as r:return json.load(r)
def post(path,data):
 r=urllib.request.Request(BASE+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=15) as f:return json.load(f)
def margin(p,atlas):
 result=float('inf')
 for road in atlas['roads']:
  a=np.asarray(road['points']);d=np.diff(a,axis=0);l=np.sum(d*d,axis=1);u=np.clip(np.sum((p-a[:-1])*d,axis=1)/np.maximum(l,1e-9),0,1)
  dist=np.linalg.norm(a[:-1]+d*u[:,None]-p,axis=1).min();result=min(result,float(dist-road['width']/2))
 return round(result,3)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profiles',nargs='+',choices=['congestion','night','fog','rattle','cargo','yield','carpool'],default=['congestion','night','fog','rattle','cargo','yield','carpool']);parser.add_argument('--seconds',type=float,default=30.);args=parser.parse_args()
    if not 10.<=args.seconds<=300.:raise ValueError('Choose 10 to 300 seconds')
    OUT=ROOT/'validation'/('alignment-'+str(time.time_ns()));OUT.mkdir(parents=True)
    owned_sid=None
    try:
        client=carla.Client('127.0.0.1',2026);client.set_timeout(20)
        results=[]
        for profile in args.profiles:
         from launch_live import memory_state
         assert memory_state()>=2,'Validation requires 2 GiB commit headroom'
         print('PREPARE',profile,flush=True);before=set((ROOT/'native-runs').rglob('*-events.jsonl'))
         old_session=(get('/state').get('scenario') or {}).get('session')
         post('/api/select',dict(profile=profile,condition='B',presentation='midterm'))
         deadline=time.monotonic()+100
         while time.monotonic()<deadline:
          s=get('/state')
          if s.get('error') and (s.get('scenario') or {}).get('session')!=old_session:raise RuntimeError(s['error'])
          if s.get('profile')==profile and s['phase']=='live' and s['frames']>2:break
          time.sleep(.3)
         else:raise RuntimeError('Scene not ready '+profile)
         atlas=get('/api/atlas');world=client.get_world();roadmap=world.get_map();owned_sid=s['scenario']['session'];post('/control',dict(mode='auto',session_id=owned_sid))
         rows=[];deadline=time.monotonic()+args.seconds*2.5+60;images=set()
         while time.monotonic()<deadline:
          s=get('/state');nav=get('/api/state');sc=s['scenario'];
          if sc['session']!=owned_sid:raise RuntimeError('Scene changed outside validation')
          p=nav['world_pose'];actual_ego=world.get_actor(nav['ego']['id']);loc=carla.Location(x=p['x'],y=p['y'],z=actual_ego.get_location().z)
          wp=roadmap.get_waypoint(loc,project_to_road=False,lane_type=carla.LaneType.Any)
          heading=None if not wp else abs((p['yaw']-wp.transform.rotation.yaw+180)%360-180)
          row=dict(traffic=s.get('traffic_alignment',[]),collision_count=sc.get('collision_count',0),elapsed=sc['elapsed_s'],speed=s['speed_kph'],lane_error=s.get('lane_error_m'),map_margin=margin(np.array([p['x'],p['y']]),atlas),actual_lane=str(wp.lane_type) if wp else None,heading=heading,actors=[])
          for a in nav.get('actors',[]):
           if a['kind']!='vehicle' or not a.get('world_pose'):continue
           ap=a['world_pose'];physical=world.get_actor(a['id']);height=physical.get_location().z if physical else loc.z;awp=roadmap.get_waypoint(carla.Location(x=ap['x'],y=ap['y'],z=height),project_to_road=False,lane_type=carla.LaneType.Any)
           row['actors'].append(dict(id=a['id'],type=a['vehicle_type'],speed=a['speed_kmh'],lane=str(awp.lane_type) if awp else None,heading=None if not awp else abs((ap['yaw']-awp.transform.rotation.yaw+180)%360-180)))
          rows.append(row)
          for sec in (0,12,28):
           if sc['elapsed_s']>=sec and sec not in images:
            with urllib.request.urlopen(BASE+'/frame.jpg',timeout=10) as f:(OUT/(profile+'-'+str(sec)+'.jpg')).write_bytes(f.read())
            images.add(sec)
          if sc['elapsed_s']>=args.seconds:break
          time.sleep(.4)
         post('/control',dict(mode='paused'))
         events=[]
         for p in set((ROOT/'native-runs').rglob('*-events.jsonl'))-before:
          events += [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
         collisions=[e for e in events if e.get('event')=='collision']
         result=dict(scope='Actual local CARLA and three-camera preview; not lab hardware or participant research',max_traffic_path_error=max((a['position_error_m'] for r in rows for a in r['traffic']),default=0),max_traffic_route_heading=max((a['heading_error_deg'] for r in rows for a in r['traffic']),default=0),max_collision_count=max(r['collision_count'] for r in rows),profile=profile,seconds=rows[-1]['elapsed'],max_lane_error=max(r['lane_error'] or 0 for r in rows),max_map_margin=max(r['map_margin'] for r in rows),max_heading=max((r['heading'] or 0) for r in rows),ego_lanes=sorted(set(str(r['actual_lane']) for r in rows)),collisions=collisions,actor_max_heading=max((a['heading'] or 0) for r in rows for a in r['actors']) if any(r['actors'] for r in rows) else None,actors_off_driving=sum(a['lane']!='Driving' for r in rows for a in r['actors']))
         results.append(result);(OUT/(profile+'.json')).write_text(json.dumps(dict(summary=result,samples=rows),indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
        (OUT/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(OUT,flush=True)
        if any(r['seconds']<args.seconds or r['max_collision_count'] or r['max_map_margin']>.3 for r in results):raise RuntimeError('Incomplete or failed alignment validation; see saved results')
    finally:
        try:
            state=get('/state')
            if (state.get('scenario') or {}).get('session')==owned_sid:post('/control',dict(mode='paused',session_id=owned_sid))
        except (OSError,ValueError):pass

if __name__=='__main__':main()
