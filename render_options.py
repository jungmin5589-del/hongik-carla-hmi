"""Persistent local CARLA/NuRec chooser. Stops only verified owned processes."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
PORT=8779
KIND='hongik-render-options'
NO_WINDOW=0x08000000 if os.name=='nt' else 0

def read_json(url,timeout=2):
    with urllib.request.urlopen(url,timeout=timeout) as response:return json.load(response)

def drive_state():
    try:
        with socket.create_connection(('127.0.0.1',8774),timeout=.15):pass
        return read_json('http://127.0.0.1:8774/state',1)
    except (OSError,ValueError):return None

def post(path,body):
    request=urllib.request.Request('http://127.0.0.1:8774'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=10) as response:
        return json.load(response) if response.status!=204 else {}

def native_live():
    configured=os.environ.get('HONGIK_NATIVE_LIVE')
    candidates=([Path(configured)] if configured else [])+[ROOT]
    candidates += [Path(f'{letter}:/Hongik-CARLA-Lab-20261107/live') for letter in 'EDF']
    for path in candidates:
        if (path/'launch_lab.py').is_file() and (path.parent/'python/python.exe').is_file() and (path.parent/'CARLA_0.9.16/CarlaUE4.exe').is_file():return path
    raise FileNotFoundError('CARLA 연구실 설치 폴더가 있는 SSD를 연결해 주세요.')

def can_switch(state):
    if state is None:return True
    if state.get('kind') not in ('hongik-native-carla','hongik-nurec'):
        raise ValueError('다른 프로그램이 주행 포트를 사용하고 있어요. 해당 프로그램은 종료하지 않았어요.')
    scenario=state.get('scenario') or {}
    if state.get('mode') in ('auto','manual') or state.get('speed_kph',0)>.5:
        raise ValueError('현재 주행을 마치고 정차한 뒤 바꿔 주세요.')
    if scenario.get('elapsed_s',0)>0 and not scenario.get('completed') and not state.get('drive_guard') and not state.get('error'):
        raise ValueError('일시정지한 주행이 남아 있어요. 현재 주행을 먼저 종료해 주세요.')
    return True

def process_command(pid):
    if not isinstance(pid,int):return ''
    command="$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(pid)+"';if($p){$p.CommandLine}"
    return subprocess.check_output(['powershell.exe','-NoProfile','-Command',command],creationflags=NO_WINDOW).decode(errors='replace')

def stop_nurec(live,python):
    owned=json.loads((live/'owned-processes.json').read_text(encoding='utf-8-sig'))
    # switch_profile verifies both the bridge command line and pinned image.
    subprocess.run([str(python),'-c','from switch_profile import stop_for_switch; stop_for_switch()'],cwd=live,check=True,creationflags=NO_WINDOW,timeout=90)
    for role in ('display','carla'):
        pid=owned.get(role);command=process_command(pid)
        match=(str(live).lower() in command.lower() and any(name in command for name in ('live_window.py','lab_viewer.py'))) if role=='display' else ('-carla-rpc-port=2016' in command and 'carlaue4' in command.lower())
        if match:subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,creationflags=NO_WINDOW,check=True)

def nurec_preflight():
    from nurec_paths import data_root,stored_file,official_root
    root=data_root();official_root()
    python=Path(os.environ.get('HONGIK_NUREC_PYTHON',r'C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe'))
    if not python.is_file():raise FileNotFoundError('기존 NuRec Python 설치가 필요해요.')
    for filename in ('scene-download.json','wide-long-scene-download.json'):
        report=json.loads((root/'reports'/filename).read_text(encoding='utf-8-sig'))
        if report.get('phase')!='download_verified':raise ValueError('NuRec 원본 검증이 필요해요.')
        if stored_file(report['local_path'],root).stat().st_size!=report['actual_bytes']:raise ValueError('NuRec 원본 크기가 달라졌어요.')
    if not (root/'live').is_dir():raise FileNotFoundError('기존 NuRec live 폴더가 필요해요.')
    return root/'live',python

class Coordinator:
    def __init__(self):
        self.lock=threading.RLock();self.status=dict(kind=KIND,phase='idle',message='화면과 상황을 선택해 주세요.',error=None)

    def update(self,**values):
        with self.lock:self.status.update(values)

    def snapshot(self):
        with self.lock:result=dict(self.status)
        state=drive_state()
        result['drive']={key:state.get(key) for key in ('kind','profile','phase','frames','measured_render_fps','lab_rig','error','mode','motion')} if state else None
        try:
            from nurec_paths import data_root
            data_root();result['ssd_connected']=True
        except (OSError,ValueError):result['ssd_connected']=False
        return result

    def select(self,body):
        if not isinstance(body,dict):raise ValueError('선택 내용을 확인해 주세요.')
        engine=body.get('engine');profile=body.get('profile');quality=body.get('quality','balanced')
        if engine not in ('carla','nurec') or profile not in ('night','congestion') or quality not in ('balanced','high'):
            raise ValueError('화면·상황·화질을 확인해 주세요.')
        operation=str(uuid.UUID(body.get('operation',str(uuid.uuid4()))))
        with self.lock:
            if self.status['phase'] in ('preparing','loading'):raise ValueError('선택한 화면을 준비하고 있어요.')
            can_switch(drive_state())
            # Resolve the target before interrupting a working source engine.
            live,python=nurec_preflight() if engine=='nurec' else (native_live(),None)
            from deploy_nurec_option import changes,NUREC
            changes(live,NUREC)
            self.status=dict(kind=KIND,phase='preparing',engine=engine,profile=profile,quality=quality,
                message='주행 환경을 확인하고 있어요.',error=None,operation=operation)
            threading.Thread(target=self.prepare,args=(engine,profile,quality,live,python),daemon=True).start()
            return dict(self.status)

    def prepare(self,engine,profile,quality,live,python):
        try:
            state=drive_state();can_switch(state)
            expected='hongik-nurec' if engine=='nurec' else 'hongik-native-carla'
            if state and state.get('kind')!=expected:
                self.update(message='기존 주행 환경을 정리하고 있어요.')
                if state['kind']=='hongik-native-carla':
                    native=native_live()
                    subprocess.run([str(native.parent/'python/python.exe'),str(native/'launch_native_carla.py'),'--stop'],cwd=native,check=True,creationflags=NO_WINDOW,timeout=45)
                else:
                    nurec,np=nurec_preflight();stop_nurec(nurec,np)
            from deploy_nurec_option import deploy,NUREC
            self.update(message='기존 파일을 백업하고 주행 코드를 반영하고 있어요.')
            deploy(live,NUREC)
            logs=ROOT/'option-runs';logs.mkdir(exist_ok=True)
            log_path=logs/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.log')
            with log_path.open('w',encoding='utf-8') as log:
                if engine=='nurec':
                    command=[str(python),str(live/'launch_nurec_lab.py'),'--profile',profile,'--quality',quality,'--no-browser']
                else:
                    from lab_viewer import monitors,surround_rect
                    command=[str(live.parent/'python/python.exe'),str(live/'launch_lab.py'),'--no-browser']
                    if not surround_rect(monitors()):command.append('--preview')
                process=subprocess.Popen(command,cwd=live,stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
            self.update(phase='loading',message='모델과 세 화면을 준비하고 있어요. 첫 실행은 시간이 걸릴 수 있어요.')
            deadline=time.monotonic()+900;selected=False;reset_session=None
            while time.monotonic()<deadline:
                current=drive_state()
                if current and current.get('kind')==expected:
                    if engine=='carla' and not selected and current['phase']!='preparing':
                        post('/api/select',dict(profile=profile,condition='B',presentation='midterm',open_navigation=False));selected=True
                    if engine=='nurec' and not selected and current.get('phase')=='live' and current.get('frames',0)>=3:
                        old=current.get('scenario') or {}
                        if old.get('completed'):
                            reset_session=old.get('session');post('/control',dict(session_id=reset_session,reset=True));selected=True
                        else:selected=True
                    if current.get('error') or current.get('phase')=='error':raise RuntimeError(current.get('error') or '주행 준비 오류')
                    same_profile=current.get('profile')==profile
                    reset_ready=not reset_session or (current.get('scenario') or {}).get('session')!=reset_session
                    ready=current.get('phase')=='live' and current.get('lab_rig') and current.get('frames',0)>=3 and same_profile and selected and reset_ready
                    if ready:
                        self.update(phase='ready',message='준비 완료 · 내비게이션에서 출발하세요.',navigation='http://127.0.0.1:8774/navigation?voice=1')
                        return
                if process.poll() not in (None,0):raise RuntimeError('실행 파일이 중단됐어요. 기록: '+str(log_path))
                time.sleep(1)
            raise TimeoutError('화면 준비가 제한 시간을 넘겼어요. 모델·GPU 실행 기록을 확인해 주세요.')
        except Exception as exc:self.update(phase='error',error=str(exc),message=str(exc))

def handler(coordinator):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,data,kind='application/json; charset=utf-8',code=200):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=urlparse(self.path).path
            try:
                if path=='/':self.send((ROOT/'render_options.html').read_bytes(),'text/html; charset=utf-8')
                elif path=='/api/health':self.send(dict(kind=KIND))
                elif path=='/api/status':self.send(coordinator.snapshot())
                elif path=='/font.woff2':self.send((ROOT/'course_ui/vendor/PretendardVariable.woff2').read_bytes(),'font/woff2')
                else:self.send_error(404)
            except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError):pass
            except (OSError,ValueError) as exc:self.send(dict(error=str(exc)),code=503)
        def do_POST(self):
            if self.path!='/api/select':self.send_error(404);return
            if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
                self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096:raise ValueError('요청 크기를 확인해 주세요.')
                self.send(coordinator.select(json.loads(self.rfile.read(length))))
            except (OSError,ValueError,RuntimeError) as exc:self.send(dict(error=str(exc)),code=400)
    return Handler

def ensure_server():
    try:
        if read_json(f'http://127.0.0.1:{PORT}/api/health',2).get('kind')!=KIND:raise RuntimeError('8779 포트는 다른 앱이 사용하고 있어요.')
        return
    except urllib.error.URLError:pass
    logs=ROOT/'option-runs';logs.mkdir(exist_ok=True)
    with (logs/('chooser-'+uuid.uuid4().hex+'.log')).open('w',encoding='utf-8') as log:
        subprocess.Popen([sys.executable,str(ROOT/'render_options.py'),'--server'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
    for _ in range(30):
        try:
            if read_json(f'http://127.0.0.1:{PORT}/api/health',1).get('kind')==KIND:return
        except OSError:time.sleep(.1)
    raise RuntimeError('화면 선택 창을 열지 못했어요.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--server',action='store_true');parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    if args.server:ThreadingHTTPServer(('127.0.0.1',PORT),handler(Coordinator())).serve_forever()
    else:
        ensure_server()
        if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{PORT}/')

if __name__=='__main__':main()
