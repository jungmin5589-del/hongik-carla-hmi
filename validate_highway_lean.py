"""Actual highway lighting/action result check after scenario workload reduction."""
import json,time,uuid,urllib.request,carla
from pathlib import Path
from benchmark_fps30 import call,wait_ready,require_memory
ROOT=Path(__file__).resolve().parent

def wait_for(predicate,seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        require_memory();s=call('/state')
        if s.get('error'):raise RuntimeError(s['error'])
        if predicate(s):return s
        time.sleep(.15)
    raise RuntimeError('Highway check timed out')

def main():
    folder=ROOT/'validation'/('highway-lean-action-'+uuid.uuid4().hex[:8]);folder.mkdir()
    original=wait_ready()
    if original['profile']!='congestion':raise RuntimeError('Select highway first')
    expected_count=12 if original.get('traffic_load')=='compact' else 16
    try:
        call('/control',{'reset':True,'mode':'paused'})
        initial=wait_for(lambda s:s['scenario']['session']!=original['scenario']['session'],15)
        call('/control',{'mode':'auto'})
        s=wait_for(lambda s:s['scenario']['onset'],30);session=s['scenario']['session']
        def command(action,event=None):return call('/api/command',dict(session_id=session,navigation_id=session+'-weaving',request_id=uuid.uuid4().hex,action=action,client_event=event or {}))
        command('study_open',{'options_visible':True});command('study_choice',{'choice':'study_highbeam'});command('study_highbeam')
        completed=wait_for(lambda s:s['scenario']['completed'],70)
        run=max((ROOT/'runs').iterdir(),key=lambda p:p.name)
        rows=[json.loads(line) for line in (run/'frames.jsonl').read_text().splitlines()]
        rows=[r for r in rows if r.get('scenario',{}).get('session')==session]
        signals=[r['high_beam_effect'] for r in rows if 'high_beam_effect' in r and r['high_beam_effect']['sequence']==1]
        stages={r['stage'] for r in signals}
        assert {0,1,2,3}.issubset(stages)
        assert any(r['on'] and r['mean_lift']>0 for r in signals)
        assert all(any(r['stage']==stage and r['on']==bool(r['carla_light_state']&int(carla.VehicleLightState.HighBeam)) for r in signals) for stage in range(4))
        assert completed['collision_proxy_count']==expected_count
        assert completed['scenario']['action']=='highbeam' and completed['scenario']['action_complete']
        out=dict(actual_carla_nurec=True,actual_iphone=False,stages=sorted(stages),proxy_count=expected_count,
            resolution=[completed['width'],completed['height']],traffic_load=completed.get('traffic_load','standard'),
            render_counts=sorted({len(r['dynamic_actor_ids']) for r in rows}),
            simulated_counts=sorted({len(r['simulated_actor_ids']) for r in rows}),completed=completed['scenario'])
        (folder/'result.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(folder=str(folder),stages=sorted(stages),completed=True)),flush=True)
    finally:call('/control',{'reset':True,'mode':'paused'})

if __name__=='__main__':main()

