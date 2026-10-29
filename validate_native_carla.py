"""Real CARLA RGB/physics QA; records local evidence, never participant claims."""
import argparse
import json
from pathlib import Path
import statistics
import time
import urllib.error
import urllib.request
import uuid
from launch_live import memory_state

BASE='http://127.0.0.1:8774'


def get(path):
    with urllib.request.urlopen(BASE+path,timeout=5) as r:return json.load(r)


def post(path,body):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=8) as r:return json.load(r)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--profile',choices=['congestion','night','fog'],required=True)
    ap.add_argument('--seconds',type=float,default=40);ap.add_argument('--action',choices=['none','study_distance','study_highbeam','study_wait','study_stop_request'],default='none')
    args=ap.parse_args()
    if memory_state()<2:raise RuntimeError('Validation needs 2 GiB commit headroom')
    root=Path(__file__).resolve().parent/'validation'/('native-'+args.profile+'-'+time.strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True,exist_ok=False)
    post('/api/select',{'profile':args.profile})
    deadline=time.monotonic()+60
    while True:
        s=get('/state')
        if s.get('error'):raise RuntimeError(s['error'])
        if s['phase']=='live' and s.get('profile')==args.profile and s['frames']>=3:break
        if time.monotonic()>deadline:raise RuntimeError('Setup timeout')
        time.sleep(.25)
    initial=get('/api/state');session=initial['session']['session_id']
    post('/control',{'mode':'auto'})
    rows=[];executed=False;captures=set();start=time.monotonic()
    with (root/'samples.jsonl').open('w',encoding='utf-8') as log:
        while time.monotonic()-start<args.seconds*1.8+90:
            s=get('/state');nav=get('/api/state');sc=s['scenario'];elapsed=sc['elapsed_s']
            if s.get('error'):raise RuntimeError(s['error'])
            if not nav['connected']:raise RuntimeError('Navigation disconnected')
            if sc['session']!=session:raise RuntimeError('Unexpected session switch')
            if s.get('lane_error_m',0)>.9:raise RuntimeError('Ego lane tracking failed: '+str(s['lane_error_m']))
            row=dict(elapsed_s=elapsed,speed_kph=s['speed_kph'],gap=sc['gap_m'],fps=s['measured_fps'],
                     lane_error_m=s.get('lane_error_m'),frame=s['frame'],completed=sc['completed'],
                     outcome=sc['outcome'],actors=nav['actors'])
            rows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
            for second in (0,9,12,16,30):
                if elapsed>=second and second not in captures:
                    with urllib.request.urlopen(BASE+'/frame.jpg',timeout=5) as r:(root/f'frame-{second:03}.jpg').write_bytes(r.read())
                    captures.add(second)
            if args.action!='none' and sc['onset'] and not executed:
                def command(action,details=None):
                    return post('/api/command',dict(session_id=session,navigation_id=session+'-weaving',request_id=uuid.uuid4().hex,
                                                   action=action,client_event=details or {}))
                try:
                    command(args.action)
                    raise AssertionError('Execution without opening and selection was accepted')
                except urllib.error.HTTPError as exc:
                    if exc.code!=400:raise
                command('study_open',{'options_visible':True});command('study_choice',{'choice':args.action})
                command(args.action);executed=True
            if sc['completed']:break
            if elapsed>=args.seconds and args.action=='none':break
            time.sleep(.5)
    post('/control',{'mode':'paused'}) if not sc['completed'] else None
    warm=[r for r in rows if r['elapsed_s']>8]
    result=dict(profile=args.profile,renderer='CARLA RGB',resolution=[s['width'],s['height']],
                target_fps=30,measured_encoded_fps_median=statistics.median(r['fps'] for r in warm) if warm else None,
                elapsed_s=sc['elapsed_s'],max_lane_error_m=max(r['lane_error_m'] for r in rows),
                min_gap_m=min(r['gap'] for r in warm) if warm else None,action=args.action,
                action_confirmed=executed,completed=sc['completed'],completion_reason=sc['completion_reason'],
                outcome=sc['outcome'],actual_video_frames=s['frames'],session=session,
                limitations='Developer QA. Not end-to-end display FPS, participant study, lab PC or 3-screen validation.')
    (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True);print('EVIDENCE',root,flush=True)
    if args.action!='none' and (not executed or sc['outcome']['phase']!='complete'):
        raise RuntimeError('The selected action did not reach the result ending')
    if args.action=='none' and args.seconds>=300 and not sc['completed']:
        raise RuntimeError('The full-duration trial did not complete; recorded as incomplete.')


if __name__=='__main__':main()
