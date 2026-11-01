"""Actual source-mode CARLA/NuRec drive; private evidence stays in validation/."""
import argparse,json,time,uuid,urllib.request
from pathlib import Path
from benchmark_fps30 import call,wait_ready,require_memory

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');args=parser.parse_args()
    folder=ROOT/'validation'/('source-natural-'+uuid.uuid4().hex[:10]);folder.mkdir()
    print(str(folder),flush=True)
    initial=wait_ready()
    if initial.get('appearance_mode')!='source':raise RuntimeError('Expected original source traffic mode')
    profile=initial['profile'];old=initial['scenario']['session']
    call('/control',dict(reset=True));deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        state=call('/state')
        if state['scenario']['session']!=old and state['scenario']['elapsed_s']==0:break
        time.sleep(.1)
    else:raise RuntimeError('Reset not acknowledged')
    session=state['scenario']['session'];run=max((ROOT/'runs').iterdir(),key=lambda p:p.name)
    captures=[0,9,12,15,30,150,290] if args.full else [0,9,12,15,25]
    samples=[];actions=[];started=time.monotonic();executed=False
    def command(action,event=None):
        result=call('/api/command',dict(session_id=session,navigation_id=session+'-weaving',request_id=uuid.uuid4().hex,
            action=action,client_event=event or {}))
        actions.append(dict(action=action,result=result));return result
    try:
        call('/control',dict(mode='auto'))
        while time.monotonic()-started<(380 if args.full else 105):
            require_memory();state=call('/state');sc=state['scenario'];samples.append(state)
            if state.get('error'):raise RuntimeError(state['error'])
            if sc['session']!=session:raise RuntimeError('Drive session changed')
            if captures and sc['elapsed_s']>=captures[0]:
                target=captures.pop(0)
                with urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg',timeout=5) as r:image=r.read()
                (folder/(str(target)+'.jpg')).write_bytes(image)
                (folder/(str(target)+'.json')).write_text(json.dumps(state,indent=2),encoding='utf-8')
                print('capture '+str(target),flush=True)
            if not args.full and not executed and sc['elapsed_s']>=27:
                command('study_open');command('study_options')
                choice='study_distance' if profile=='fog' else 'study_support'
                command('study_choice',dict(choice=choice));command(choice);executed=True
            if sc['completed']:break
            time.sleep(.2)
        call('/control',dict(mode='paused'))
        rows=[json.loads(line) for line in (run/'frames.jsonl').read_text().splitlines()]
        rows=[r for r in rows if r['scenario']['session']==session and r['scenario']['elapsed_s']>0]
        if len(rows)<20 or not sc['completed']:raise RuntimeError('Drive did not finish with enough actual neural frames')
        if captures:raise RuntimeError('Missing requested captures: '+str(captures))
        assert all('31001' not in r['dynamic_actor_ids'] for r in rows)
        assert all(r['scenario']['source_faithful'] for r in rows)
        assert all(r['dimensions']==[1280,720] for r in rows)
        if profile=='fog':
            assert any(r.get('fog_effect',{}).get('applied') for r in rows)
            assert all(r['scenario']['fog']['beta']>=.1999 for r in rows if r['scenario']['elapsed_s']>=15)
        result=dict(actual_carla_nurec=True,profile=profile,full_300s=args.full,resolution=[1280,720],
            completed=sc['completed'],reason=sc['completion_reason'],elapsed_s=sc['elapsed_s'],actions=actions,
            physics_displacement_m=__import__('math').dist(samples[0]['carla_position'],samples[-1]['carla_position']),
            max_cross_track_m=max(s.get('cross_track_m',0) for s in samples),
            max_camera_physical_weight=max(r['camera_stabilization']['physical_weight'] for r in rows),
            actual_fps=(len(rows)-1)/(rows[-1]['monotonic']-rows[0]['monotonic']),
            actual_browser_audio=False,original_capture_seconds=20)
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (folder/'samples.json').write_text(json.dumps(samples),encoding='utf-8')
        print(json.dumps(result),flush=True)
    finally:call('/control',dict(mode='paused'))

if __name__=='__main__':main()
