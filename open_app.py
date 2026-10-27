"""One lightweight entry for all three trials; no model starts before selection."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8775/'
(ROOT/'launches').mkdir(exist_ok=True)

try:
    from open_mobile import ensure_gateway
    ensure_gateway()
except (OSError,RuntimeError) as error:
    # A handset setup failure must not prevent the original PC experiment.
    print('휴대폰 연결 서버: '+str(error),flush=True)
def health():
    try:
        with urllib.request.urlopen(URL+'api/status',timeout=2) as r:return json.load(r).get('kind')=='nurec-scenario-hub'
    except (OSError,ValueError):return False

if not health():
    with socket.socket() as probe:
        probe.settimeout(.4)
        if probe.connect_ex(('127.0.0.1',8775))==0:raise RuntimeError('Port 8775 belongs to another app; left it untouched')
    log=(ROOT/'launches'/('app-hub-'+time.strftime('%Y%m%d-%H%M%S')+'.log')).open('w',encoding='utf-8')
    process=subprocess.Popen([sys.executable,str(ROOT/'app_hub.py')],cwd=ROOT,
        stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000,
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='1'))
    (ROOT/'app-hub-process.json').write_text(json.dumps(dict(pid=process.pid,script=str(ROOT/'app_hub.py'))),encoding='utf-8')
    deadline=time.monotonic()+12
    while not health():
        if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Scenario app could not start; inspect app-hub log')
        time.sleep(.2)
if '--no-browser' not in sys.argv:webbrowser.open(URL)
print(URL,flush=True)
