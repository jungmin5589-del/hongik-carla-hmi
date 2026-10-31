"""CARLA-only full recordings, with existing scene sounds aligned to real events."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from timed_jpeg_capture import TimedJpegCapture
from launch_live import memory_state
from scene_soundtrack import render

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'recording-tools'))
import imageio_ffmpeg
BASE='http://127.0.0.1:8774'
COURSE=Path.home()/'Desktop/홍익대/2026 2학기/휴먼 자율주행 인터렉션 디자인'
NAMES={'carpool':'취객_접근과_문두드림','yield':'횡단보도_보행자','rattle':'차량_이상음','congestion':'4차로_정체','night':'야간_졸음운전','fog':'짙은_안개'}

def call(path,body=None):
    request=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={} if body is None else {'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)

def record(profile,folder):
    call('/api/select',{'profile':profile});deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        s=call('/state')
        if s.get('error'):raise RuntimeError(s['error'])
        if s['profile']==profile and s['phase']=='live' and s['mode']=='paused' and not s['scenario']['completed'] and s['frames']>5:break
        time.sleep(.5)
    else:raise RuntimeError('Scene preparation timeout')
    time.sleep(1);initial=s;folder.mkdir();capture=TimedJpegCapture(folder);capture.start();timeline=[];finished=None;next_log=0
    try:
        call('/control',{'mode':'auto'})
        print(json.dumps(dict(event='recording_started',profile=profile,folder=str(folder)),ensure_ascii=False),flush=True)
        with (folder/'timeline.jsonl').open('w',encoding='utf-8',buffering=1) as trace:
            deadline=time.monotonic()+420;next_memory=0
            while time.monotonic()<deadline:
                s=call('/state');sc=s['scenario'];at=time.monotonic()-capture.started
                item=dict(recording_s=at,state=s);timeline.append(item);trace.write(json.dumps(item,ensure_ascii=False)+'\n')
                if sc['session']!=initial['scenario']['session']:raise RuntimeError('Session changed')
                if s.get('error') or capture.errors:raise RuntimeError(str(s.get('error') or capture.errors))
                if at>=next_memory:
                    if memory_state()<2:raise RuntimeError('Existing 2 GiB commit guard reached')
                    next_memory=at+5
                if sc['elapsed_s']>=next_log:
                    print(json.dumps(dict(event='recording',profile=profile,elapsed_s=sc['elapsed_s'],frames=len(capture.frames)),ensure_ascii=False),flush=True);next_log=sc['elapsed_s']+15
                if sc['completed']:finished=s;time.sleep(1.5);break
                time.sleep(.075)
        if finished is None:raise RuntimeError('Scene did not finish')
    finally:
        try:
            s=call('/state')
            if not s['scenario']['completed']:call('/control',{'mode':'paused'})
        finally:capture.stop()
    print(json.dumps(dict(event='encoding',profile=profile),ensure_ascii=False),flush=True)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();picture=folder/'picture.mp4';capture.encode(ffmpeg,picture)
    first=capture.frames[0]['time_s'];duration=capture.ended-first
    # Events and video share the same monotonic capture clock.
    soundtrack=folder/'scene-sound.wav';sound=render(timeline,capture.ended,soundtrack)
    output=folder/(NAMES[profile]+'_720p_장면소리.mp4')
    with (folder/'mux.log').open('w') as log:
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','warning','-n','-i',str(picture),'-ss',str(first),'-i',str(soundtrack),
            '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart',str(output)],stdout=log,stderr=subprocess.STDOUT,check=True)
    with (folder/'decode.log').open('w') as log:
        subprocess.run([ffmpeg,'-v','error','-xerror','-i',str(output),'-map','0:v:0','-map','0:a:0','-f','null','-'],stdout=log,stderr=subprocess.STDOUT,check=True)
    with output.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
    result=dict(profile=profile,path=str(output),duration_s=round(duration,2),source_frames=len(capture.frames),
        source_mean_fps=len(capture.frames)/duration,sha256=digest,decode_verified=True,complete=True,
        video='Actual CARLA RGB, no navigation pixels',audio=sound,
        response='Default waiting/maintaining; no AI panel/choice actions')
    (folder/'result.json').write_text(json.dumps(dict(result=result,initial=initial,final=finished),ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profiles',nargs='+',choices=list(NAMES),default=list(NAMES));args=parser.parse_args()
    if call('/state').get('kind')!='hongik-native-carla':raise RuntimeError('Native CARLA required')
    name=time.strftime('%Y%m%d-%H%M%S')+'-CARLA-scenes';root=ROOT.parent/'recordings'/name;root.mkdir()
    delivery=COURSE/'시나리오별 주행영상'/name;delivery.mkdir(parents=True)
    results=[];error=None
    print(json.dumps(dict(event='suite_started',folder=str(root),course_shortcuts=str(delivery)),ensure_ascii=False),flush=True)
    try:
        for i,profile in enumerate(args.profiles):
            if shutil.disk_usage(root).free<4*1024**3:raise RuntimeError('Less than 4 GiB free on capture SSD')
            result=record(profile,root/(f'{i+1:02d}-'+profile));results.append(result)
            (delivery/(Path(result['path']).stem+'.url')).write_text('[InternetShortcut]\nURL='+Path(result['path']).as_uri()+'\n',encoding='utf-8')
            (delivery/'recordings.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(dict(event='saved',profile=profile,path=result['path'],duration_s=result['duration_s']),ensure_ascii=False),flush=True)
    except Exception as ex:error=str(ex);raise
    finally:
        (root/'index.json').write_text(json.dumps(dict(results=results,error=error),ensure_ascii=False,indent=2),encoding='utf-8')
        lines=['# CARLA 시나리오 전체 영상','',
            '영상은 CARLA 도로 카메라 실녹화이며 내비 화면은 없습니다. 소리는 기존 대사/발소리/문 두드림/기계음을 실제 장면 이벤트 시간에 맞춰 합쳤습니다. PC 스피커 녹음은 아닙니다.',
            '현재 native 서버는 -nosound로 실행되므로 기존 엔진/도로 배경음은 없습니다. 없는 엔진음을 추가하지 않았습니다.',
            '기본 대기/유지로 실제 종료까지 기록했습니다. 30fps 출력은 실제 30fps 성능 보증이 아닙니다.',
            '원본 MP4는 D에 있고 수업 폴더에는 바로가기와 이 목록을 둡니다.','']
        lines += [f"- [{NAMES[r['profile']]} · {r['duration_s']:.1f}초]({Path(r['path']).as_uri()})" for r in results]
        if error:lines+=['','중단: '+error]
        (delivery/'영상 목록.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
