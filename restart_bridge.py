"""Reload this trial's Python bridge without loading a second GPU model."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
PYTHON=Path(r'C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe')
with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=5) as r:state=json.load(r)
profile=state.get('profile','night')
assert profile in ('night','congestion','fog')
owned=json.loads((ROOT/'owned-processes.json').read_text(encoding='utf-8-sig'))
pid=owned['bridge']
query="$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(pid)+"';if($p){$p.CommandLine}"
command=subprocess.check_output(['powershell.exe','-NoProfile','-Command',query],creationflags=0x08000000).decode(errors='replace')
assert 'scene_bridge.py' in command and str(ROOT).lower() in command.lower()
subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],check=True,capture_output=True,creationflags=0x08000000)
time.sleep(.5)
log=(ROOT/'launches'/('bridge-reload-'+time.strftime('%Y%m%d-%H%M%S')+'.log')).open('w',encoding='utf-8')
p=subprocess.Popen([str(PYTHON),str(ROOT/'scene_bridge.py'),'--profile',profile],cwd=ROOT,
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='1'),
    stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
owned['bridge']=p.pid
(ROOT/'owned-processes.json').write_text(json.dumps(owned,indent=2))
print('Restarted owned bridge',p.pid,profile)
