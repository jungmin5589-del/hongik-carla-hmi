"""Private short baseline capture and actual straight-path/performance check."""
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'recording-tools'))
import imageio_ffmpeg
from timed_jpeg_capture import TimedJpegCapture


def call(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:8774'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'} if body is not None else {})
    with urllib.request.urlopen(req,timeout=5) as response:data=response.read()
    return json.loads(data) if data else None


def main():
    initial=call('/state')
    if initial.get('night_mode')!='straight' or initial['phase']!='live' or initial.get('error'):
        raise RuntimeError('The straight-mode night scene is not ready.')
    call('/control',{'reset':True})
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        ready=call('/state')
        if ready['scenario']['session']!=initial['scenario']['session'] and ready['scenario']['elapsed_s']==0:break
        time.sleep(.1)
    else:raise RuntimeError('Could not reset the trial.')
    folder=ROOT.parent/'recordings'/('straight-weaving-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    video=folder/'NuRec-straight-weaving.mp4'
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    trace=[]
    capture=TimedJpegCapture(folder)
    try:
        capture.start()
        time.sleep(.5)
        call('/control',{'mode':'auto'})
        started=time.monotonic()
        first=call('/state')
        try:
            while time.monotonic()-started<46.5:
                state=call('/state')
                if state.get('error'):raise RuntimeError(state['error'])
                if state['scenario']['session']!=ready['scenario']['session']:raise RuntimeError('Trial changed.')
                trace.append(dict(wall_s=time.monotonic()-started,state=state))
                if capture.errors:raise RuntimeError(str(capture.errors))
                time.sleep(.2)
        finally:call('/control',{'mode':'paused'})
    finally:
        capture.stop()
        (folder/'states.json').write_text(json.dumps(trace,ensure_ascii=False),encoding='utf-8')
    capture.encode(ffmpeg,video)
    final=trace[-1]['state']
    nav=call('/api/state')
    lateral=[r['state']['scenario']['lateral_m'] for r in trace if r['state']['scenario']['elapsed_s']>=10.]
    checks=dict(straight_ego=max(r['state']['cross_track_m'] for r in trace)<.5,
        lead_weaves=min(lateral)<-2.3 and max(lateral)>-1.3,
        no_crash=all('crash' not in r['state']['scenario'] and not r['state'].get('post_collision_hold') for r in trace),
        no_action=all(r['state']['scenario']['action'] is None for r in trace),
        schematic_matches=nav['ego']['lane_index']==1 and len(nav['road']['lanes'])==2)
    (folder/'states.json').write_text(json.dumps(trace,ensure_ascii=False),encoding='utf-8')
    inspection=subprocess.run([ffmpeg,'-hide_banner','-i',str(video)],capture_output=True,text=True)
    (folder/'video-inspection.txt').write_text(inspection.stderr,encoding='utf-8')
    duration_match=re.search(r'Duration: (\d+):(\d+):([\d.]+)',inspection.stderr)
    if not duration_match:raise RuntimeError('No valid video duration.')
    h,m,s=map(float,duration_match.groups());duration=h*3600+m*60+s
    decoded=subprocess.run([ffmpeg,'-v','error','-i',str(video),'-f','null','-'],capture_output=True,text=True)
    checks['video_decodes']=decoded.returncode==0 and not decoded.stderr.strip() and abs(duration-45)<5.
    fps=(final['frames']-first['frames'])/(trace[-1]['wall_s']-trace[0]['wall_s'])
    result=dict(passed=False,functional_checks_passed=all(checks.values()),checks=checks,
        visual_review_pending=True,video=str(video),duration_s=duration,
        received_render_fps=fps,max_ego_cross_track_m=max(r['state']['cross_track_m'] for r in trace),
        lead_lateral_range_m=[min(lateral),max(lateral)],single_front_camera=True,
        resolution=[initial['width'],initial['height']],fps_setting=10,three_screens_tested=False,
        recording_timing='actual JPEG arrival timing; 30fps container repeats frames; no interpolation',
        source='actual CARLA actor state and NuRec render, not synthetic controller input')
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for seconds,name in [(3,'start'),(16,'boundary-left'),(20,'boundary-right'),(35,'later')]:
        subprocess.run([ffmpeg,'-v','error','-n','-ss',str(seconds),'-i',str(video),'-frames:v','1',
            str(folder/(name+'.jpg'))],check=True,capture_output=True)
    call('/control',{'reset':True})
    print(json.dumps(dict(folder=str(folder),**result),ensure_ascii=False),flush=True)
    if not all(checks.values()):raise RuntimeError('Actual baseline validation failed.')


if __name__=='__main__':main()
