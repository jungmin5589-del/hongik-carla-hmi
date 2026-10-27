"""Record each actual route, then deliver verified MP4s to the course folder."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
import urllib.request
from pathlib import Path

from benchmark_fps30 import wait_ready
from record_full_drive import main as record
from record_full_drive import state

ROOT=Path(__file__).resolve().parent
COURSE=Path.home()/'Desktop/홍익대/2026 2학기/휴먼 자율주행 인터렉션 디자인'


def main():
    destination=COURSE/'시나리오별 주행영상'/(time.strftime('%Y-%m-%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    destination.mkdir(parents=True,exist_ok=False)
    output=[]
    # Record the already loaded source first; model switches are sequential.
    profiles=[('fog','03_짙은안개_720p.mp4'),('night','02_야간_졸음운전_720p.mp4'),('congestion','01_4차로_정체_720p.mp4')]
    try:
        for profile,name in profiles:
            print(json.dumps(dict(event='preparing_profile',profile=profile,destination=str(destination)),ensure_ascii=False),flush=True)
            subprocess.run([sys.executable,str(ROOT/'launch_live.py'),'--profile',profile,'--quality','high','--traffic-load','standard','--no-browser'],cwd=ROOT,check=True)
            ready=wait_ready();assert ready['profile']==profile and ready['width']==1280 and ready['height']==720
            with urllib.request.urlopen('http://127.0.0.1:8774/api/state',timeout=10) as response:nav=json.load(response)
            with urllib.request.urlopen('http://127.0.0.1:8774/api/atlas',timeout=10) as response:atlas=json.load(response)
            assert nav['actors'] and all('world_pose' in actor for actor in nav['actors'])
            assert atlas['context_source'] and 'buildings' in atlas
            print(json.dumps(dict(event='navigation_ready',profile=profile,vehicles=len(nav['actors']),buildings=len(atlas['buildings'])),ensure_ascii=False),flush=True)
            result=record();source=Path(result['video']);target=destination/name
            (source.parent/'navigation-state.json').write_text(json.dumps(nav,ensure_ascii=False,indent=2),encoding='utf-8')
            (source.parent/'navigation-atlas.json').write_text(json.dumps(atlas,ensure_ascii=False,indent=2),encoding='utf-8')
            if shutil.disk_usage(destination).free<source.stat().st_size+512*1024**2:raise RuntimeError('Insufficient course-folder space; the original recording remains on D.')
            if target.exists():raise RuntimeError('Refusing to overwrite an existing recording')
            shutil.copy2(source,target)
            with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            assert digest==result['sha256']
            output.append(dict(profile=profile,file=name,duration_s=result['duration_s'],resolution=result['resolution'],sha256=digest,
                complete_route=True,silent=True))
            (destination/'영상목록.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(dict(event='delivered',profile=profile,file=str(target),duration_s=result['duration_s']),ensure_ascii=False),flush=True)
    finally:
        lines=['# 시나리오별 실제 주행 녹화','',
            '현재 CARLA·NuRec 실행의 출발부터 구간 끝 정차까지 녹화했습니다. 대응 옵션을 선택하지 않은 기본 주행입니다.',
            '720p H.264 MP4, 음성 없는 주행 화면. 원래 프레임 도착 시간을 보존하며 30fps 파일에 반복 프레임으로 저장합니다. 실제 30fps 렌더링을 뜻하지 않습니다.',
            '원본 JPEG와 상세 실행 로그는 D 드라이브의 recordings 폴더에 보존합니다. 이 폴더는 수업용 로컬 자료이며 GitHub에는 업로드하지 않습니다.','']
        lines += [f"- {item['file']} · {item['duration_s']:.1f}초 · 전체 구간 완료" for item in sorted(output,key=lambda item:item['file'])]
        (destination/'읽어주세요.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert len(output)==3
    print(json.dumps(dict(event='all_recordings_delivered',folder=str(destination),videos=output),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
