"""Live-only outcome check. Runs just the selected controlled local scene."""
import argparse
import json
import time
import uuid
import urllib.request
from pathlib import Path
from launch_live import memory_state

ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8774'
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=5) as response:return json.load(response)
def post(path,body):
    request=urllib.request.Request(BASE+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=5) as response:return None if response.status==204 else json.load(response)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--action',choices=['horn','highbeam','direct','maintain'],default='horn');args=ap.parse_args()
    state=get('/state')
    if state.get('profile')!='night_pedestrian' or state.get('phase')!='live':raise RuntimeError('Prepare the live NuRec pedestrian scene first')
    if memory_state()<2.:raise RuntimeError('Validation needs 2GiB commit headroom')
    folder=ROOT/'validation'/('nurec-yield-'+args.action+'-'+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir()
    post('/control',dict(reset=True));deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        current=get('/state')
        if current['scenario']['session']!=state['scenario']['session'] and current['mode']=='paused':break
        time.sleep(.1)
    else:raise RuntimeError('Reset did not complete')
    post('/control',dict(mode='auto'));started=time.monotonic();rows=[];chosen=False;direct_done=False
    phases=set();wait_positions=[];last_frame=None;frame_times=[]
    try:
        while time.monotonic()-started<150:
            state=get('/state');sc=state['scenario'];phase=sc['yielding']['phase'];age=time.monotonic()-started
            row=dict(wall_s=age,state=state);rows.append(row)
            if state.get('error'):raise RuntimeError(state['error'])
            if sc['collision_count']:raise RuntimeError('Unexpected pedestrian contact')
            if phase in ('mutual_wait','crossing','clearance') and state['speed_kph']>.5:raise RuntimeError('Car did not hold for pedestrian')
            if state['frames']!=last_frame:frame_times.append((age,state['frames']));last_frame=state['frames']
            if phase not in phases or phase=='mutual_wait' and len(wait_positions) in (0,5,10):
                phases.add(phase)
                with urllib.request.urlopen(BASE+'/frame.jpg',timeout=5) as r:(folder/(f'{age:05.1f}-{phase}.jpg')).write_bytes(r.read())
                print(phase,round(age,1),state['speed_kph'],sc['gap_m'],flush=True)
            if phase=='mutual_wait':
                wait_positions.append(sc['yielding']['offset_m'])
                if len(wait_positions)>=12 and not chosen:
                    session=sc['session']
                    def command(action,**details):return post('/api/command',dict(session_id=session,navigation_id=session+'-weaving',request_id=uuid.uuid4().hex,action=action,client_event=details))
                    action={'horn':'study_horn','highbeam':'study_highbeam','direct':'study_direct','maintain':'study_wait'}[args.action]
                    command('study_open',options_visible=True);command('study_choice',choice=action);command(action);chosen=True;action_at=time.monotonic()
                if args.action=='direct' and chosen and not direct_done and time.monotonic()-action_at>5:
                    command('study_direct_done');direct_done=True
            if sc['completed']:break
            time.sleep(.5)
        else:raise RuntimeError('Outcome did not finish within the live validation limit')
        summary=dict(completed=sc['completed'],phase=sc['yielding']['phase'],action=sc['action'],
            collision_count=sc['collision_count'],wall_s=round(age,2),phases=sorted(phases),
            actual_hesitation_range_m=round(max(wait_positions)-min(wait_positions),3),
            car_held_for_crossing=True,actual_native_and_nurec_drive=True,not_participant_research=True)
        (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(summary,flush=True)
    finally:
        post('/control',dict(mode='paused'))
        (folder/'states.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':main()
