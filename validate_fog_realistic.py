"""Five-minute actual drive with native context and same-frame fog evidence."""
import json,time,uuid,urllib.request
from pathlib import Path
from benchmark_fps30 import call,wait_ready,require_memory
from fog_scene import ONSET_SECONDS,BASE_GAP_M
ROOT=Path(__file__).resolve().parent

def review_drive(rows,state,captures):
    """Review actual recorded frames independently from live control/polling."""
    applied=[r for r in rows if r.get('fog_effect',{}).get('applied')]
    assert captures==[5,9,10.5,11,12,15,30,130,290]
    assert rows[-1]['scenario']['elapsed_s']>=300 and rows[-1]['scenario']['completed']
    assert applied and all(r['fog_effect'].get('native_composite') for r in applied)
    assert all(not r.get('fog_effect',{}).get('applied') for r in rows if r['scenario']['elapsed_s']<=ONSET_SECONDS)
    assert all(r['scenario']['fog']['beta']>=.20 for r in rows if r['scenario']['elapsed_s']>=12)
    assert all(r['scenario']['target_gap_m']==BASE_GAP_M for r in rows)
    # Allow the measured departure transient, then require the closer gap
    # by the time the dense fog is established.
    assert all(5.<r['scenario']['gap_m']<13. for r in rows if 5<r['scenario']['elapsed_s']<30)
    assert all(5.<r['scenario']['gap_m']<11. for r in rows if 12<r['scenario']['elapsed_s']<30)
    assert all('7' in r['simulated_actor_ids'] for r in rows if 5<r['scenario']['elapsed_s']<20)
    assert all(r['dimensions']==[state['width'],state['height']] for r in rows)
    intervals=[b['monotonic']-a['monotonic'] for a,b in zip(rows,rows[1:])]
    return dict(actual_carla_nurec=True,full_300_seconds=True,resolution=[state['width'],state['height']],
        proxy_count=state['collision_proxy_count'],lead='6',native_context=['7','36'],captures=captures,onset_s=ONSET_SECONDS,target_gap_m=BASE_GAP_M,
        actual_fps=(len(rows)-1)/(rows[-1]['monotonic']-rows[0]['monotonic']),
        interval_max_ms=max(intervals)*1000,completed=rows[-1]['scenario']['completed'],
        approximate_atmospheric_composite=True,actual_iphone=False)

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
        session=state['scenario']['session'];pending=[5,9,10.5,11,12,15,30,130,290];captures=[]
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
        out=review_drive(rows,state,captures)
        (folder/'result.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
    finally:call('/control',dict(reset=True,mode='paused'))

if __name__=='__main__':main()
