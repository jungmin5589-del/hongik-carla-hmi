"""Stable local scenario chooser; owns no CARLA or voice model itself."""
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from profile_sources import manifest_name,source_id
from performance_presets import PRESETS

ROOT=Path(__file__).resolve().parent
PYTHON=Path('C:/CARLA_0.9.16/diagnostics/nurec-env/Scripts/python.exe')
PORT=8775
PROFILES={'congestion':'정체·서행','night':'야간 불안정한 앞차','fog':'짙은 안개'}
NO_WINDOW=0x08000000

def read_drive():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=2) as r:return json.load(r)
    except (OSError,ValueError):return None

def control(body):
    request=urllib.request.Request('http://127.0.0.1:8774/control',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=5) as r:r.read()

class Coordinator:
    def __init__(self,runner=None):
        self.lock=threading.RLock();self.runner=runner or self.prepare
        self.status=dict(kind='nurec-scenario-hub',phase='choose',profile=None,error=None,launch_id=None)
        self.requests={}

    def state(self):
        with self.lock:return dict(self.status)

    def select(self,body):
        profile=body.get('profile');duration=body.get('duration_s',300);request=body.get('request_id')
        performance=body.get('performance','standard')
        if not isinstance(performance,str) or performance not in PRESETS:raise ValueError('영상 설정을 다시 선택해 주세요.')
        if profile not in PROFILES:raise ValueError('시나리오를 먼저 선택해 주세요.')
        if type(duration) is not int or duration not in (300,450,600):raise ValueError('체험 시간을 다시 선택해 주세요.')
        if profile!='congestion' and duration!=300:raise ValueError('이 시나리오는 고정된 길이를 사용합니다.')
        if not isinstance(request,str) or not 1<=len(request)<=128:raise ValueError('요청 ID가 필요합니다.')
        with self.lock:
            signature=(profile,duration,performance)
            if request in self.requests:
                prior=self.requests[request]
                if prior['signature']!=signature:raise ValueError('같은 요청을 다른 시나리오로 바꿀 수 없습니다.')
                return dict(prior['result'])
            if self.status['phase'] not in ('choose','ready','failed'):
                raise ValueError('선택한 체험을 준비하고 있어요. 잠시 기다려 주세요.')
            launch_id=uuid.uuid4().hex
            self.status=dict(kind='nurec-scenario-hub',phase='starting',profile=profile,error=None,launch_id=launch_id,performance=performance)
            result=dict(launch_id=launch_id,profile=profile)
            self.requests[request]=dict(signature=signature,result=result)
            if len(self.requests)>128:self.requests.pop(next(iter(self.requests)))
            threading.Thread(target=self.run,args=(launch_id,profile,duration),daemon=True).start()
            return result

    def publish(self,launch_id,**values):
        with self.lock:
            if self.status['launch_id']==launch_id:self.status.update(values)

    def run(self,launch_id,profile,duration):
        try:self.runner(launch_id,profile,duration)
        except Exception as exc:
            self.publish(launch_id,phase='failed',error=str(exc))

    def prepare(self,launch_id,profile,duration):
        with self.lock:preset=PRESETS[self.status.get('performance','standard')]
        if not ROOT.parent.is_dir():raise RuntimeError('외장 D 드라이브 연결을 확인해 주세요.')
        manifest=manifest_name(profile)
        data=json.loads((ROOT.parent/'reports'/manifest).read_text(encoding='utf-8'))
        if data.get('phase')!='download_verified':raise RuntimeError('장면 원본을 확인하지 못했습니다.')
        log_path=ROOT/'launches'/('app-'+time.strftime('%Y%m%d-%H%M%S')+'-'+launch_id[:8]+'.log')
        with log_path.open('w',encoding='utf-8') as log:
            process=subprocess.Popen([str(PYTHON),str(ROOT/'launch_live.py'),'--profile',profile,'--no-browser',
                '--quality',preset['quality'],'--traffic-load',preset['traffic_load']],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW,
                env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='1'))
        deadline=time.monotonic()+660
        while time.monotonic()<deadline:
            if process.poll() not in (None,0):
                details=log_path.read_text(encoding='utf-8',errors='replace')
                if '16 GiB' in details or 'headroom' in details:
                    raise RuntimeError('시작에 필요한 메모리가 부족해요. 사용하지 않는 앱을 닫고 다시 시도해 주세요.')
                raise RuntimeError('체험을 시작하지 못했어요. 외장 SSD와 실행 환경을 확인해 주세요.')
            drive=read_drive()
            if (drive and drive.get('profile')==profile and drive.get('scene_id')==source_id(profile)
                    and drive.get('traffic_load','standard')==preset['traffic_load']
                    and (profile!='night' or drive.get('night_mode')=='straight')):
                phase=drive.get('phase')
                self.publish(launch_id,phase='warming' if phase!='live' else 'starting')
                if drive.get('error'):self.publish(launch_id,phase='warming')
                if phase=='live' and drive.get('frames',0)>=3 and not drive.get('error'):
                    old_session=drive['scenario']['session']
                    settings={'duration_s':duration} if profile=='congestion' and drive['scenario'].get('layout')!='four_lane_blockade' else {'reset':True}
                    settings['quality']=preset['quality']
                    control(settings)
                    reset_deadline=time.monotonic()+15
                    while time.monotonic()<reset_deadline:
                        ready=read_drive()
                        if (ready and ready['scenario']['session']!=old_session and ready['scenario']['elapsed_s']==0
                                and ready['mode']=='paused' and (ready.get('width'),ready.get('height'))==preset['size']):
                            self.publish(launch_id,phase='ready',navigation_url='http://127.0.0.1:8774/navigation',error=None)
                            return
                        time.sleep(.2)
                    raise RuntimeError('출발 상태를 준비하지 못했어요. 다시 시도해 주세요.')
            time.sleep(1)
        raise RuntimeError('장면 준비가 오래 걸리고 있어요. 연결 상태를 확인하고 다시 시도해 주세요.')

def handler(coordinator):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def send(self,data,kind='application/json; charset=utf-8',code=200):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=urlparse(self.path).path
            if path=='/api/status':self.send(coordinator.state());return
            assets={'/':('app_home.html','text/html'),'/app.js':('app_home.js','application/javascript'),'/app.css':('app_home.css','text/css')}
            if path not in assets:self.send_error(404);return
            name,kind=assets[path]
            try:self.send((ROOT/name).read_bytes(),kind+'; charset=utf-8')
            except OSError:self.send_error(503)
        def do_POST(self):
            if self.path!='/api/select':self.send_error(404);return
            if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
                self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=2048:raise ValueError('요청 크기가 올바르지 않습니다.')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('올바른 시나리오 요청이 필요합니다.')
                self.send(coordinator.select(body))
            except (ValueError,TypeError) as exc:self.send({'error':str(exc)},code=400)
    return Handler

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',PORT),handler(Coordinator()))
    print(f'Scenario chooser http://127.0.0.1:{PORT}/',flush=True)
    server.serve_forever()
