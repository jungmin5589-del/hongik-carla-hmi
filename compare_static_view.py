"""Compare view selection against bypass in one loaded process and scene."""
import json,subprocess,sys,time,uuid
from pathlib import Path
from benchmark_fps30 import wait_ready,call,require_memory
ROOT=Path(__file__).resolve().parent

def bypass(enabled):
    require_memory()
    subprocess.run(['wsl.exe','-d','Ubuntu-22.04','-u','root','--exec','docker','exec',
        'nurec-live-20261019','sh','-c',
        'touch /tmp/nurec-static-view-bypass' if enabled else 'rm -f /tmp/nurec-static-view-bypass'],check=True,creationflags=0x08000000)

def main():
    folder=ROOT/'validation'/('static-view-ab-'+uuid.uuid4().hex[:8]);folder.mkdir()
    wait_ready();results=[]
    for name,disabled,seconds in [('bypass-first',True,35),('view-cache',False,35),('bypass-repeat',True,35)]:
        bypass(disabled)
        call('/control',dict(reset=True,mode='paused'));time.sleep(2.)
        before=set((ROOT/'validation').glob('fps30-*'))
        subprocess.run([sys.executable,str(ROOT/'benchmark_fps30.py'),'--seconds',str(seconds),
            '--label','same-process-'+name],check=True,creationflags=0x08000000)
        added=set((ROOT/'validation').glob('fps30-*'))-before
        if len(added)!=1:raise RuntimeError('Ambiguous result folder')
        result_file=next(iter(added))/'result.json';r=json.loads(result_file.read_text());r['evidence']=str(result_file)
        r['bypass_enabled']=disabled;results.append(r)
    bypass(True)
    report=dict(same_process=True,actual_carla_nurec=True,interpolated_frames=False,results=results)
    (folder/'result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(folder=str(folder),fps=[r['renderer_fps'] for r in results],p95=[r['interval_p95_ms'] for r in results])),flush=True)

if __name__=='__main__':main()
