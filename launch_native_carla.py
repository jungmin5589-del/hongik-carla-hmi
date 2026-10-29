"""Start the CARLA-only app, preserving the separate NuRec entry points."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

from launch_live import require_startup_memory

ROOT=Path(__file__).resolve().parent
NO_WINDOW=0x08000000
OWNED=ROOT/'native-owned.json'
PYTHON=Path(sys.executable)
CARLA=Path(os.environ.get('CARLA_ROOT','C:/CARLA_0.9.16'))


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(.2)
        return sock.connect_ex(('127.0.0.1',port))==0


def process_command(pid):
    if not isinstance(pid,int):return ''
    cmd="$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(pid)+"';if($p){$p.CommandLine}"
    return subprocess.check_output(['powershell.exe','-NoProfile','-Command',cmd],creationflags=NO_WINDOW).decode(errors='replace')


def stop_native():
    owned=json.loads(OWNED.read_text(encoding='utf-8-sig')) if OWNED.is_file() else {}
    for role in ('display','app','carla'):
        pid=owned.get(role);cmd=process_command(pid)
        expected={'display':'native_drive_window.py','app':'native_carla.py','carla':str(CARLA/'CarlaUE4.exe')}[role]
        if expected.lower() in cmd.lower() and (role!='carla' or '-carla-rpc-port=2026' in cmd):
            subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,creationflags=NO_WINDOW,check=False)
    print('Stopped only the recorded CARLA-native application processes.')


def main():
    if '--stop' in sys.argv:
        stop_native();return
    if listening(8774):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=3) as r:state=json.load(r)
        except Exception as exc:raise RuntimeError('Port 8774 belongs to another app; leave it untouched.') from exc
        if state.get('kind')=='hongik-native-carla':
            ensure_phone()
            webbrowser.open('http://127.0.0.1:8774/');return
        # The existing NuRec stop script verifies recorded process identities.
        if not (ROOT/'owned-processes.json').is_file():
            raise RuntimeError('Another untracked driving session is running on 8774.')
        subprocess.run([str(PYTHON),str(ROOT/'stop_live.py')],cwd=ROOT,check=True)
        if listening(8774):raise RuntimeError('The previous session is still stopping. Retry after it closes.')
    owned=json.loads(OWNED.read_text(encoding='utf-8-sig')) if OWNED.is_file() else {}
    logs=ROOT/'native-runs'/('launch-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid()))
    logs.mkdir(parents=True,exist_ok=False)
    if listening(2026):
        command=process_command(owned.get('carla'))
        if str(CARLA/'CarlaUE4.exe').lower() not in command.lower() or '-carla-rpc-port=2026' not in command:
            raise RuntimeError('Port 2026 is occupied by an untracked CARLA. It was not changed.')
    else:
        require_startup_memory()
        existing=subprocess.check_output(['tasklist','/FI','IMAGENAME eq CarlaUE4-Win64-Shipping.exe','/FO','CSV','/NH'],creationflags=NO_WINDOW).decode(errors='replace')
        if 'carlaue4-win64-shipping.exe' in existing.lower():
            raise RuntimeError('A different CARLA world is running. Close it before starting this app.')
        with (logs/'carla.log').open('w') as log:
            p=subprocess.Popen([str(CARLA/'CarlaUE4.exe'),'-carla-rpc-port=2026','-RenderOffScreen','-nosound'],
                               cwd=CARLA,stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
        owned['carla']=p.pid
        OWNED.write_text(json.dumps(owned),encoding='utf-8')
        # First engine startup can take longer than an app page. Keep that visible.
        deadline=time.monotonic()+180
        while not listening(2026):
            if p.poll() is not None or time.monotonic()>deadline:
                raise RuntimeError('CARLA engine did not start. Check native-runs launch logs.')
            time.sleep(.5)
    with (logs/'app.log').open('w',encoding='utf-8') as log:
        p=subprocess.Popen([str(PYTHON),'-u',str(ROOT/'native_carla.py'),'--no-browser'],cwd=ROOT,
                           stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW,
                           env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='1'))
    owned['app']=p.pid;OWNED.write_text(json.dumps(owned),encoding='utf-8')
    for _ in range(60):
        if p.poll() is not None:raise RuntimeError('Native app startup failed. Check native-runs logs.')
        if listening(8774):
            ensure_phone()
            webbrowser.open('http://127.0.0.1:8774/');return
        time.sleep(.25)
    raise RuntimeError('Native app did not become ready.')


def ensure_phone():
    try:
        from open_mobile import ensure_gateway
        ensure_gateway()
    except (OSError,RuntimeError) as exc:
        print('휴대폰 연결 준비: '+str(exc),flush=True)


if __name__=='__main__':main()
