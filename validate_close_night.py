"""Actual close-following drive and confirmed distance-increase outcome.

Runtime evidence/video stay on D, outside Git. Capture repeats received frames
in a 30fps video container; it never proves a 30fps neural-rendering rate.
"""
import json,time,uuid,urllib.request,subprocess
from pathlib import Path
from benchmark_fps30 import call,wait_ready,require_memory
from night_weaving import BoundaryWeaving
from timed_jpeg_capture import TimedJpegCapture

ROOT=Path(__file__).resolve().parent

def main():
    folder=ROOT/'validation'/('close-night-live-'+uuid.uuid4().hex[:8]);folder.mkdir()
    print(json.dumps(dict(event='waiting',folder=str(folder))),flush=True)
    initial=wait_ready()
    if initial.get('night_mode')!='straight' or initial['profile']!='night':
        raise RuntimeError('Select straight night first.')
    capture=TimedJpegCapture(folder);capturing=False
    try:
        call('/control',dict(reset=True,mode='paused'))
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=call('/state')
            if state['scenario']['session']!=initial['scenario']['session']:break
            time.sleep(.1)
        else:raise RuntimeError('Reset not acknowledged.')
        session=state['scenario']['session'];pending=[5,12,20,30]
        capture.start();capturing=True
        call('/control',dict(mode='auto'));started=time.monotonic()
        while time.monotonic()-started<50:
            require_memory();state=call('/state');sc=state['scenario']
            if state.get('error'):raise RuntimeError(state['error'])
            if sc['session']!=session:raise RuntimeError('Trial changed.')
            if pending and sc['elapsed_s']>=pending[0]:
                label=str(pending.pop(0))
                (folder/(label+'.jpg')).write_bytes(urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg',timeout=5).read())
                print(json.dumps(dict(event='close_following',seconds=sc['elapsed_s'],gap_m=sc['gap_m'])),flush=True)
            if sc['elapsed_s']>=35:break
            time.sleep(.15)
        else:raise RuntimeError('Baseline did not progress.')
        action_at=state['scenario']['elapsed_s']
        def command(action,**event):
            return call('/api/command',dict(action=action,session_id=session,navigation_id=session+'-weaving',
                request_id=uuid.uuid4().hex,client_event=event))
        command('study_open');command('study_options')
        command('study_choice',choice='study_distance');command('study_distance')
        print(json.dumps(dict(event='distance_increase_requested')),flush=True)
        deadline=time.monotonic()+85
        while time.monotonic()<deadline:
            require_memory();state=call('/state')
            if state.get('error'):raise RuntimeError(state['error'])
            if state['scenario']['session']!=session:raise RuntimeError('Trial changed.')
            if state['scenario']['completed']:break
            time.sleep(.2)
        else:raise RuntimeError('Distance result did not complete.')
        call('/control',dict(mode='paused'));capture.stop();capturing=False
        run=max((ROOT/'runs').iterdir(),key=lambda p:p.name)
        rows=[json.loads(line) for line in (run/'frames.jsonl').read_text().splitlines()]
        rows=[r for r in rows if r['scenario']['session']==session]
        baseline=[r for r in rows if 15.<r['scenario']['elapsed_s']<action_at]
        if not baseline:raise RuntimeError('Missing baseline frames.')
        gaps=[r['scenario']['gap_m'] for r in baseline]
        lateral=[r['scenario']['lateral_m'] for r in baseline]
        outcome=state['scenario']['outcome']
        checks=dict(actual_carla_nurec=True,close_gap=3.<min(gaps)<=max(gaps)<6.5,
            close_target=all(r['scenario']['target_gap_m']==BoundaryWeaving.BASE_GAP for r in baseline),
            straight_ego=max(r['cross_track_m'] for r in rows)<.5,
            lead_weaves=min(lateral)<-2.3 and max(lateral)>-1.3,
            no_crash=all('crash' not in r['scenario'] and not r.get('post_collision_hold') for r in rows),
            distance_achieved=outcome['status']=='achieved' and outcome['observed_s']>=12.,
            end_message=bool(outcome['message']) and state['scenario']['completed'],
            native_720p=all(r['dimensions']==[1280,720] for r in rows))
        result=dict(checks=checks,passed=all(checks.values()),gap_range_m=[min(gaps),max(gaps)],
            target_gap_m=BoundaryWeaving.BASE_GAP,widen_target_m=BoundaryWeaving.WIDE_GAP,
            outcome=outcome,actual_live_drive=True,actual_iphone=False,three_screens_tested=False)
        (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        ffmpeg=next((ROOT.parent/'recording-tools/imageio_ffmpeg/binaries').glob('ffmpeg*.exe'))
        video=folder/'close-following-and-distance.mp4';capture.encode(str(ffmpeg),video)
        decoded=subprocess.run([str(ffmpeg),'-v','error','-i',str(video),'-f','null','-'],capture_output=True,text=True)
        if decoded.returncode or decoded.stderr.strip():raise RuntimeError('Recorded drive does not fully decode.')
        print(json.dumps(dict(event='complete',folder=str(folder),**result)),flush=True)
        if not result['passed']:raise RuntimeError('Actual close-following validation failed.')
    finally:
        if capturing:capture.stop()
        call('/control',dict(reset=True,mode='paused'))

if __name__=='__main__':main()
