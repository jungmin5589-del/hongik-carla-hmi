"""Post-repair operator QA only. Real scene outputs always stay on D:."""
import argparse
import json
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path


BASE='http://127.0.0.1:8774'


def call(path, body=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'} if body is not None else {})
    with urllib.request.urlopen(req,timeout=5) as response:
        data=response.read()
    return json.loads(data) if data else None  # /control returns HTTP 204.


def wait_for(predicate, seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        state=call('/state')
        if state.get('error'):raise RuntimeError(state['error'])
        if predicate(state):return state
        time.sleep(.2)
    raise RuntimeError('Live validation timed out; inspect the retained run.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Reset the ready night trial and execute the crash branch.')
    args=parser.parse_args()
    if not args.run:parser.error('--run is required; this validator changes the selected trial.')
    probe=subprocess.check_output(['powershell.exe','-NoProfile','-Command',
        "$v=Get-Volume -DriveLetter D;[pscustomobject]@{health=[string]$v.HealthStatus;operational=@($v.OperationalStatus|ForEach-Object{[string]$_})}|ConvertTo-Json"],creationflags=0x08000000)
    volume=json.loads(probe.decode('utf-8-sig'))
    if volume['health']!='Healthy' or 'OK' not in volume['operational']:
        raise RuntimeError('D: is not healthy; no trial or output was started.')
    state=call('/state')
    if (state.get('profile')!='night' or state.get('phase')!='live' or state.get('frames',0)<3
            or 'crash' not in state.get('scenario',{})):
        raise RuntimeError('Prepare the deployed night profile with live frames first.')
    root=Path(r'D:\CARLA-Maps\NuRec-OneScene-20261018\live')
    output=root/'validation'/('night-overtake-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    output.mkdir(parents=True,exist_ok=False)
    result={'passed':False,'actual_carla_nurec':True,'visual_quality_reviewed':False,'actual_iphone_checked':False}
    try:
        old=state['scenario']['session']
        call('/control',{'reset':True})
        wait_for(lambda s:s['scenario']['session']!=old and s['scenario']['elapsed_s']==0,15)
        call('/control',{'mode':'auto'})
        state=wait_for(lambda s:s['scenario']['onset'],180)
        session=state['scenario']['session']
        if not state['scenario']['overtake']['available']:raise RuntimeError(state['scenario']['overtake']['unavailable_reason'])
        def command(action,**event):
            return call('/api/command',dict(session_id=session,navigation_id=session+'-weaving',
                request_id=uuid.uuid4().hex,action=action,client_event=event))
        command('study_open',options_visible=True)
        command('study_choice',choice='study_overtake')
        if call('/state')['scenario']['action'] is not None:raise RuntimeError('Choosing alone acted on the vehicle.')
        command('study_overtake')
        with (output/'states.jsonl').open('w',encoding='utf-8') as trace:
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                state=call('/state');trace.write(json.dumps(state,ensure_ascii=False)+'\n');trace.flush()
                if state.get('error'):raise RuntimeError(state['error'])
                if state['scenario']['completed']:break
                time.sleep(.25)
            else:raise RuntimeError('Crash/result sequence did not finish.')
        sc=state['scenario'];crash=sc['crash'];outcome=sc['outcome']
        checks=dict(contact=crash['primary_collision_verified'],
            rendered_stages={'primary_impact','secondary_impact','aftermath'}.issubset(crash['rendered_stages']),
            full_observation=outcome['observed_s']>=12.,stopped=state['speed_kph']<.5,
            result=outcome['status']=='collision' and outcome['phase']=='complete',
            ended=sc['completion_reason']=='action_outcome')
        nav=call('/api/state')
        checks['not_destination_arrival']=not nav['route']['arrived']
        checks['navigation_notice']='충돌' in nav['session']['navigation']['research_event']['description']
        result.update(checks=checks,passed=all(checks.values()),session=session)
        if not result['passed']:raise RuntimeError('At least one actual integration check failed.')
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        try:call('/control',{'mode':'paused'})
        except OSError:pass
        (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(str(output),flush=True)


if __name__=='__main__':main()
