"""Short real fog run: onset, retained native lead and updated composition path."""
import json,time,uuid,urllib.request
from pathlib import Path
from benchmark_fps30 import call,wait_ready,require_memory
ROOT=Path(__file__).resolve().parent

def main():
    folder=ROOT/'validation'/('fog-lean-runtime-'+uuid.uuid4().hex[:8]);folder.mkdir()
    print(json.dumps({'event':'waiting','folder':str(folder)}),flush=True)
    original=wait_ready()
    if original['profile']!='fog':raise RuntimeError('Select fog first')
    try:
        call('/control',{'reset':True,'mode':'paused','quality':'high'})
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            s=call('/state')
            if s['scenario']['session']!=original['scenario']['session']:break
            time.sleep(.1)
        else:raise RuntimeError('Reset not acknowledged')
        session=s['scenario']['session'];call('/control',{'mode':'auto'});started=time.monotonic()
        print(json.dumps({'event':'driving','seconds':70}),flush=True)
        while time.monotonic()-started<70:
            require_memory();s=call('/state')
            if s.get('error'):raise RuntimeError(s['error'])
            time.sleep(.2)
        call('/control',{'mode':'paused'});run=max((ROOT/'runs').iterdir(),key=lambda p:p.name)
        rows=[json.loads(line) for line in (run/'frames.jsonl').read_text().splitlines()]
        rows=[r for r in rows if r.get('scenario',{}).get('session')==session]
        stats={}
        for name,low,high in [('clear',3,25),('developing',40,68)]:
            window=[r for r in rows if low<=r['scenario']['elapsed_s']<=high]
            if len(window)<10:raise RuntimeError('Insufficient actual fog frames')
            import statistics
            stats[name]=dict(actual_fps=(len(window)-1)/(window[-1]['monotonic']-window[0]['monotonic']),
                composite_median_ms=statistics.median([r['fog_effect']['composite_ms'] for r in window if r.get('fog_effect',{}).get('composite_ms') is not None]) if any(r.get('fog_effect',{}).get('composite_ms') is not None for r in window) else None,
                frame_count=len(window))
        assert any(r.get('fog_effect',{}).get('native_composite') for r in rows)
        assert all(r['fog_effect'].get('native_composite') for r in rows if r.get('fog_effect',{}).get('applied'))
        assert all(not r.get('fog_effect',{}).get('applied') for r in rows if r['scenario']['elapsed_s']<30)
        assert s['collision_proxy_count']==1 and s['scenario']['onset']
        with urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg') as response:(folder/'actual-developing-fog.jpg').write_bytes(response.read())
        out=dict(actual_carla_nurec=True,resolution=[s['width'],s['height']],short_test=True,full_300_seconds=False,
            proxy_count=1,state=s,windows=stats,fps30_achieved=False,
            native_composite_frames=sum(bool(r.get('fog_effect',{}).get('native_composite')) for r in rows))
        (folder/'result.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(folder=str(folder),windows=stats)),flush=True)
    finally:call('/control',{'reset':True,'mode':'paused'})

if __name__=='__main__':main()
