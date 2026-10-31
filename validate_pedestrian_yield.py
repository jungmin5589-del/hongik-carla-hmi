"""Real CARLA development QA. No frame-rate or participant-effect claims."""
import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

from launch_live import memory_state

BASE='http://127.0.0.1:8774'
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=10) as reply:return reply.read()
def post(path,data):
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as reply:return json.load(reply)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=['notice','support','wait','none'],default='notice');args=parser.parse_args()
    if memory_state()<2:raise RuntimeError('Validation requires 2 GiB commit headroom')
    folder=Path(__file__).resolve().parent/'validation'/('pedestrian-'+args.action+'-'+time.strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True,exist_ok=False)
    post('/api/select',{'profile':'yield'});deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        state=json.loads(get('/state'))
        if state.get('error'):raise RuntimeError(state['error'])
        if state['phase']=='live' and state.get('profile')=='yield' and state['frames']>3:break
        time.sleep(.3)
    else:raise TimeoutError('Scene preparation')
    sid=state['scenario']['session'];post('/control',{'mode':'auto'})
    action_sent=False;phases=[];last='';max_crossing_speed=0.;deadline=time.monotonic()+115
    with (folder/'states.jsonl').open('w',encoding='utf-8') as log:
        while time.monotonic()<deadline:
            state=json.loads(get('/state'));sc=state['scenario'];phase=sc['yielding']['phase']
            if state.get('error'):raise RuntimeError(state['error'])
            log.write(json.dumps(state,ensure_ascii=False)+'\n');log.flush()
            if phase!=last:
                phases.append(phase);last=phase;print(phase,sc['elapsed_s'],state['speed_kph'],flush=True)
                (folder/(phase+'.jpg')).write_bytes(get('/frame.jpg'))
            if phase=='mutual_wait' and not action_sent and sc['yielding']['wait_s']>=3.:
                (folder/'mutual-wait-gesture.jpg').write_bytes(get('/frame.jpg'))
                if args.action!='none':
                    action={'notice':'study_horn','support':'study_distance','wait':'study_wait'}[args.action]
                    for command,details in [('study_open',{'options_visible':True}),('study_choice',{'choice':action}),(action,{})]:
                        post('/api/command',dict(session_id=sid,navigation_id=sid+'-weaving',request_id=uuid.uuid4().hex,action=command,client_event=details))
                action_sent=True
            if phase in ('mutual_wait','crossing','clearance'):
                max_crossing_speed=max(max_crossing_speed,state['speed_kph'])
                if state['speed_kph']>.6:raise AssertionError('Vehicle moved during pedestrian crossing')
            if sc['completed']:
                if not all(p in phases for p in ('mutual_wait','crossing','clearance','resume','complete')):raise AssertionError(phases)
                if state['speed_kph']>=.5:raise AssertionError('Trial did not end stopped')
                result=dict(action=args.action,phases=phases,max_crossing_speed_kph=max_crossing_speed,final=state,
                            scope='Actual CARLA actors/API/RGB QA; browser and physical audio not measured')
                (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                print(str(folder),flush=True);return
            time.sleep(.25)
    raise TimeoutError('Pedestrian trial did not complete; evidence retained in '+str(folder))

if __name__=='__main__':main()
