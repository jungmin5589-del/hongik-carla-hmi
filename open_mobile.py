"""Start only the paired handset gateway; never starts or resets CARLA."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PYTHON=ROOT.parent/'mobile-env/Scripts/python.exe'
URL='http://127.0.0.1:8776/'


def gateway_status():
    try:
        with urllib.request.urlopen(URL+'health',timeout=2) as r:return json.load(r)
    except (OSError,ValueError):return {}


def health():
    value=gateway_status();return value.get('kind')=='hongik-mobile' and value.get('polling',True)


def stop_unhealthy_gateway():
    record=json.loads((ROOT/'mobile-process.json').read_text(encoding='utf-8'));pid=record.get('pid')
    if type(pid) is not int or pid<=0:raise RuntimeError('휴대폰 서버의 실행 정보를 확인하지 못했습니다.')
    query="$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(pid)+"';if($p){$p.CommandLine}"
    command=subprocess.check_output(['powershell.exe','-NoProfile','-Command',query],creationflags=0x08000000).decode(errors='replace')
    expected=str(ROOT/'mobile_gateway.py').replace('\\','/').lower()
    if expected not in command.replace('\\','/').lower():raise RuntimeError('다른 프로세스는 종료하지 않았습니다. 휴대폰 서버 실행 정보를 확인해 주세요.')
    subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],check=True,capture_output=True,creationflags=0x08000000)


def ensure_gateway():
    value=gateway_status()
    if value.get('kind')=='hongik-mobile':
        if value.get('polling',True):return
        stop_unhealthy_gateway()
    if not PYTHON.is_file():raise RuntimeError('휴대폰 연결용 실행 환경이 없습니다. D 드라이브 연결을 확인해 주세요.')
    for port in (8776,8777):
        with socket.socket() as probe:
            probe.settimeout(.3)
            if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError(f'Port {port} belongs to another app; left untouched')
    (ROOT/'launches').mkdir(exist_ok=True)
    log=(ROOT/'launches'/('mobile-'+time.strftime('%Y%m%d-%H%M%S')+'.log')).open('w',encoding='utf-8')
    p=subprocess.Popen([str(PYTHON),str(ROOT/'mobile_gateway.py')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000,
                       env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2'))
    (ROOT/'mobile-process.json').write_text(json.dumps(dict(pid=p.pid,script=str(ROOT/'mobile_gateway.py'))),encoding='utf-8')
    deadline=time.monotonic()+15
    while not health():
        if p.poll() is not None or time.monotonic()>deadline:raise RuntimeError('휴대폰 연결 서버가 시작되지 않았습니다. mobile 실행 로그를 확인해 주세요.')
        time.sleep(.2)


if __name__=='__main__':
    ensure_gateway()
    if '--no-browser' not in sys.argv:webbrowser.open(URL+'connect')
    print(URL+'connect',flush=True)
