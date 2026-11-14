"""Live app monitoring. Uses the owned CARLA world, no motion output."""
import argparse,json,time,urllib.request
from pathlib import Path
from launch_live import memory_state

def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',default='congestion');p.add_argument('--seconds',type=float,default=75.);p.add_argument('--action');a=p.parse_args()
 if memory_state()<2.:raise RuntimeError('Validation needs 2 GiB commit headroom')
 def req(path,body=None):
  r=urllib.request.Request('http://127.0.0.1:8774'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(r,timeout=6) as f:return json.load(f)
 participant=req('/api/participant/current').get('participant')
 if not participant or not participant.get('name','').startswith('QA-control-rebuild'):
  req('/api/participant',{'name':'QA-control-rebuild-20261114'})
 req('/api/select',{'profile':a.profile,'condition':'B','language':'ko'})
 deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  try:
   s=req('/state')
   if s.get('phase')=='live' and s.get('profile')==a.profile:break
   if s.get('error'):raise RuntimeError(s['error'])
  except TimeoutError:pass
  time.sleep(.5)
 else:raise RuntimeError('Preparation timed out')
 print('SCENE READY',a.profile,s.get('runtime_revision'),flush=True)
 req('/control',{'mode':'auto'});rows=[];failure=None;sent=False;wall_start=time.monotonic();deadline=time.monotonic()+a.seconds*2+45
 try:
  while time.monotonic()<deadline:
   s=req('/state');sc=s.get('scenario',{})
   row={k:s.get(k) for k in ['mode','speed_kph','lane_error_m','control_cycle_ms','actor_projection_ms','planning_ms','drive_guard','measured_fps','physical_vehicles']};row.update(outcome_status=sc.get('outcome',{}).get('status'),study_phase=sc.get('study',{}).get('phase'),wall_elapsed_s=round(time.monotonic()-wall_start,3),elapsed=sc.get('elapsed_s'),gap=sc.get('gap_m'),collisions=sc.get('collision_count'),completed=sc.get('completed'))
   alignment=s.get('traffic_alignment',[]);row['max_fleet_error']=max((i['position_error_m'] for i in alignment),default=0.)
   rows.append(row)
   if row['collisions'] or row['drive_guard'] or row['max_fleet_error']>1.5:failure='collision, guard or fleet departure';print('FAIL',row,flush=True);break
   if a.action and sc.get('onset') and not sent:
    sid=sc['session'];nav=req('/api/state')['session']['navigation']['id']
    def command(action,**details):
     reply=req('/api/command',{'session_id':sid,'navigation_id':nav,'action':action,'request_id':str(time.time_ns()),'client_event':details})
     return reply
    command('study_open',options_visible=True);command('study_options',options_visible=True);command('study_choice',choice=a.action);command(a.action);sent=True;print('ACTION',a.action,flush=True)
   if a.action and row['completed']:
    if row['outcome_status']!='achieved':failure='action did not achieve its physical result'
    break
   if not a.action and row['elapsed']>=a.seconds:break
   time.sleep(.4)
  else:failure='wall timeout'
 finally:
  try:req('/control',{'mode':'paused'})
  except Exception:pass
 result={'profile':a.profile,'action':a.action,'failure':failure,'rows':rows}
 out=Path(__file__).parent.parent/'lab-reports'/('scene-'+a.profile+'-'+(a.action or 'baseline')+'-'+str(int(a.seconds))+'s.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('RESULT',len(rows),'samples',rows[-1],flush=True)
 if failure:raise RuntimeError(failure)
if __name__=='__main__':main()
