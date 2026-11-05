"""Owned native CARLA run; records actual action outcomes, not participant results."""
import argparse
import json
from pathlib import Path
import time
import urllib.request
import uuid
from launch_live import memory_state

ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8774'
def call(path,body=None):
    request=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('profile');ap.add_argument('action');ap.add_argument('--condition',default='B');args=ap.parse_args()
    if memory_state()<2:raise RuntimeError('Validation requires 2 GiB commit headroom')
    folder=ROOT/'validation'/('midterm-'+args.profile+'-'+args.action+'-'+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir(parents=True,exist_ok=False)
    call('/api/select',dict(profile=args.profile,condition=args.condition,presentation='midterm'))
    start=time.monotonic()
    while True:
        state=call('/state')
        if state.get('error'):raise RuntimeError(state['error'])
        if state['phase']=='live' and state.get('profile')==args.profile and state['frames']>3:break
        if time.monotonic()-start>90:raise RuntimeError('Setup timeout')
        time.sleep(.5)
    sid=state['scenario']['session']
    def command(action,details=None):
        queued=call('/api/command',dict(session_id=sid,navigation_id=sid+'-weaving',request_id=uuid.uuid4().hex,action=action,client_event=details or {}))
        reply=call('/api/reply?session='+sid+'&id='+queued['command_id'])
        if not reply['accepted']:raise RuntimeError(reply['message'])
    call('/control',{'mode':'auto'});sent=False;view=False;captures=set();rows=[];start=time.monotonic()
    try:
        with (folder/'samples.jsonl').open('w',encoding='utf-8') as output:
            while time.monotonic()-start<210:
                if memory_state()<2:raise RuntimeError('Validation commit headroom below 2 GiB')
                state=call('/state');nav=call('/api/state');sc=state['scenario'];study=sc['study']
                if state.get('error'):raise RuntimeError(state['error'])
                if sc['session']!=sid:raise RuntimeError('Unexpected session change')
                if sc.get('collision_count',0):raise RuntimeError('Physical collision during request')
                rows.append(state);output.write(json.dumps(state,ensure_ascii=False)+'\n');output.flush()
                if sc['onset'] and not sent:
                    if args.action.startswith('study_fixed_'):command(args.action)
                    else:
                        command('study_presented',{'surface':'developer protocol validation'})
                        command('study_open',{'options_visible':True});command('study_choice',{'choice':args.action});command(args.action)
                    sent=True
                if study['action']=='inspect' and study['phase'] in ('applying','observing') and not view:
                    command('study_view_opened',{'surface':'developer protocol; not browser visual verification'});view=True
                for tag,ready in (('onset',sc['onset']),('applying',study['phase']=='applying'),('result',study['phase']=='observing'),('complete',sc['completed'])):
                    if ready and tag not in captures:
                        with urllib.request.urlopen(BASE+'/frame.jpg',timeout=5) as response:(folder/(tag+'.jpg')).write_bytes(response.read())
                        captures.add(tag)
                if sc['completed']:break
                time.sleep(.35)
        outcome=sc['outcome'];summary=dict(profile=args.profile,action=args.action,condition=args.condition,session=sid,
            completed=sc['completed'],outcome=outcome,collision_count=sc.get('collision_count'),
            elapsed_s=sc['elapsed_s'],resolution=[state['width'],state['height']],
            frames=state['frames'],horn_count=sc.get('horn_count'),gap_m=sc.get('gap_m'),
            source='Actual CARLA engine and request API; browser layout and audio playback not asserted')
        (folder/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(summary,ensure_ascii=False),flush=True);print('EVIDENCE',str(folder),flush=True)
        if not sent or not sc['completed']:raise RuntimeError('Request did not complete')
        if outcome.get('status') not in ('achieved','partial'):raise RuntimeError('Request failed: '+str(outcome.get('status')))
    finally:
        if not call('/state').get('scenario',{}).get('completed'):call('/control',{'mode':'paused'})

if __name__=='__main__':main()
