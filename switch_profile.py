"""Switch only recorded bridge/renderer. Keep owned CARLA and native display."""
import json
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
IMAGE='nvcr.io/nvidia/nre/nre-ga@sha256:97f43e7130c5636ce3e80ea3184d97f56a87fdd989b05cce42230881dbdea284'


def stop_for_switch(keep_renderer=False):
    owned=json.loads((ROOT/'owned-processes.json').read_text(encoding='utf-8-sig'))
    pid=owned.get('bridge')
    if not isinstance(pid,int):raise RuntimeError('Cannot switch an untracked bridge')
    query="$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(pid)+"';if($p){$p.CommandLine}"
    cmd=subprocess.check_output(['powershell.exe','-NoProfile','-Command',query],creationflags=0x08000000).decode(errors='replace')
    if 'scene_bridge.py' not in cmd or str(ROOT).lower() not in cmd.lower():
        raise RuntimeError('Recorded bridge identity changed; left it untouched')
    subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,check=True,creationflags=0x08000000)
    if keep_renderer:
        time.sleep(.5)
        return
    shell="container=nurec-live-20261019; image=$(docker inspect --format '{{.Config.Image}}' $container 2>/dev/null) || exit 0; [ \"$image\" = '"+IMAGE+"' ] || exit 1; docker stop --timeout 10 $container >/dev/null; for i in $(seq 1 40); do docker inspect $container >/dev/null 2>&1 || exit 0; sleep 0.5; done; exit 1"
    subprocess.run(['wsl.exe','-d','Ubuntu-22.04','-u','root','--exec','bash','-lc',shell],check=True,creationflags=0x08000000)
    time.sleep(1.)
