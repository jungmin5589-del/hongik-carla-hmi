"""Bounded live-engine check; evidence stays local under validation/."""
import argparse
import json
from pathlib import Path
import time
import urllib.request

from launch_live import memory_state

BASE='http://127.0.0.1:8774'


def get(path):
    with urllib.request.urlopen(BASE+path,timeout=8) as r:
        return r.read()


def state():
    s=json.loads(get('/state'))
    if s.get('error'):raise RuntimeError(s['error'])
    return s


def post(path,body):
    request=urllib.request.Request(BASE+path,json.dumps(body).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=8) as r:
        data=r.read()
        return json.loads(data) if data else {}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--action',choices=['inspect','avoid','stop','delegate'],default='stop')
    args=ap.parse_args()
    if memory_state()<2:raise RuntimeError('Live validation requires 2 GiB commit headroom')
    folder=Path(__file__).resolve().parent/'validation'/('cargo-'+args.action+'-'+time.strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True,exist_ok=False)
    s=state();previous_session=(s.get('scenario') or {}).get('session')
    if s['phase']!='live' or s.get('profile')!='cargo':
        post('/api/select',dict(profile='cargo'))
    else:
        post('/control',dict(reset=True))
    end=time.monotonic()+100
    while time.monotonic()<end:
        s=state()
        if s['phase']=='live' and s.get('profile')=='cargo' and s['scenario']['session']!=previous_session and s['scenario']['elapsed_s']==0 and s['frames']>=3:break
        time.sleep(.4)
    else:raise RuntimeError('Cargo preparation timed out')
    motion_second=-1.
    sid=s['scenario']['session'];loaded_actor=s['scenario']['cargo']['actor_id'];events=[];shots=set();executed=False
    def command(action,details=None):
        return post('/api/command',dict(action=action,session_id=sid,navigation_id=sid+'-weaving',
                                       request_id=f'{action}-{time.monotonic_ns()}',client_event=details or {}))
    post('/control',dict(mode='auto'))
    try:
        end=time.monotonic()+150
        while time.monotonic()<end:
            s=state();sc=s['scenario'];events.append(s)
            if sc['session']!=sid:raise RuntimeError('Session changed during validation')
            elapsed=sc['elapsed_s'];c=sc['cargo']
            if sc['onset'] and c['height_m'] is not None:
                assert -.3<c['height_m']<4., 'Payload left the bounded drop area'
                assert abs(c['right_m'])<4., 'Payload flew outside its lane area'
            assert c['actor_id']==loaded_actor, 'Visible payload was replaced at release'
            if 8.7<=elapsed<=12.2 and elapsed-motion_second>=.18:
                (folder/('motion-'+str(round(elapsed,2))+'.jpg')).write_bytes(get('/frame.jpg'));motion_second=elapsed
            label='approach' if 8<=elapsed<9 else 'falling' if sc['onset'] and c['fall_age_s']<.8 else 'obstacle' if sc['onset'] and c['fall_age_s']>=3 else None
            if label and label not in shots:
                (folder/(label+'.jpg')).write_bytes(get('/frame.jpg'));shots.add(label)
            if sc['onset'] and c['fall_age_s']>=5. and not executed:
                command('study_open',dict(options_visible=False));command('study_options')
                choice={'inspect':'study_inspect','avoid':'study_avoid','stop':'study_stop_request','delegate':'study_wait'}[args.action]
                command('study_choice',dict(choice=choice));command(choice);executed=True
            if sc['completed']:
                (folder/'result.jpg').write_bytes(get('/frame.jpg'))
                (folder/'telemetry.json').write_text(json.dumps(events,ensure_ascii=False),encoding='utf-8')
                assert sc['collision_count']==0, 'Unexpected collision in nominal run'
                assert sc['outcome']['status']=='achieved',sc['outcome']
                assert s['speed_kph']<.5,s['speed_kph']
                heights=[v['scenario']['cargo']['height_m'] for v in events if v['scenario']['cargo']['height_m'] is not None]
                assert max(heights)-min(heights)>.6, 'Physical fall not observed'
                assert min(heights)>-.3, 'Prop fell through the road'
                print(json.dumps(dict(evidence=str(folder),action=args.action,fall_height_change_m=round(max(heights)-min(heights),2),
                                      final=sc,fps=s['measured_fps']),ensure_ascii=False),flush=True)
                return
            time.sleep(.1)
        raise RuntimeError('Action outcome did not finish within live validation deadline')
    finally:
        post('/control',dict(mode='paused')) if not state()['scenario']['completed'] else None
        if events:(folder/'telemetry.json').write_text(json.dumps(events,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__':main()
