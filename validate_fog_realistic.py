"""Five-minute actual drive with native context and same-frame fog evidence."""
import json,time,uuid,urllib.request
from pathlib import Path
from benchmark_fps30 import call,wait_ready,require_memory
ROOT=Path(__file__).resolve().parent

def main():
    folder=ROOT/'validation'/('fog-natural-live-'+uuid.uuid4().hex[:8]);folder.mkdir()
    print(json.dumps(dict(folder=str(folder),event='waiting')),flush=True)
    original=wait_ready()
    if original['profile']!='fog' or original['collision_proxy_count']!=3:raise RuntimeError('Expected revised three-actor fog scene')
    try:
        call('/control',dict(reset=True,mode='paused'))
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=call('/state')
            if state['scenario']['session']!=original['scenario']['session']:break
            time.sleep(.1)
        else:raise RuntimeError('Reset not acknowledged')
        session=state['scenario']['session'];pending=[10,29,45,65,130,220,290];captures=[]
        call('/control',dict(mode='auto'));started=time.monotonic()
        print(json.dumps(dict(event='driving',duration_s=300)),flush=True)
        while time.monotonic()-started<350:
            require_memory();state=call('/state');sc=state['scenario']
            if state.get('error'):raise RuntimeError(state['error'])
            if sc['session']!=session:raise RuntimeError('Trial changed during validation')
            if pending and sc['elapsed_s']>=pending[0]:
                target=pending.pop(0)
                with urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg',timeout=5) as response:data=response.read()
                (folder/(str(target)+'.jpg')).write_bytes(data)
                (folder/(str(target)+'.json')).write_text(json.dumps(state,indent=2))
                captures.append(target);print(json.dumps(dict(event='capture',at=target,beta=sc['fog']['beta'])),flush=True)
            if sc['completed']:break
            time.sleep(.15)
        call('/control',dict(mode='paused'))
        run=max((ROOT/'runs').iterdir(),key=lambda p:p.name)
        rows=[json.loads(s) for s in (run/'frames.jsonl').read_text().splitlines()]
        rows=[r for r in rows if r['scenario']['session']==session]
        applied=[r for r in rows if r.get('fog_effect',{}).get('applied')]
        assert len(captures)==7 and state['scenario']['elapsed_s']>=300
        assert all(r['fog_effect'].get('native_composite') for r in applied)
        assert all(not r.get('fog_effect',{}).get('applied') for r in rows if r['scenario']['elapsed_s']<30)
        assert all('7' in r['simulated_actor_ids'] for r in rows if 5<r['scenario']['elapsed_s']<20)
        intervals=[b['monotonic']-a['monotonic'] for a,b in zip(rows,rows[1:])]
        out=dict(actual_carla_nurec=True,full_300_seconds=True,resolution=[state['width'],state['height']],
            proxy_count=3,lead='6',native_context=['7','36'],captures=captures,
            actual_fps=(len(rows)-1)/(rows[-1]['monotonic']-rows[0]['monotonic']),
            interval_max_ms=max(intervals)*1000,completed=state['scenario']['completed'],
            approximate_atmospheric_composite=True,actual_iphone=False)
        (folder/'result.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
    finally:call('/control',dict(reset=True,mode='paused'))

if __name__=='__main__':main()
