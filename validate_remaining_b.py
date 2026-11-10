"""Unregistered local CARLA action checks; detailed evidence stays outside Git."""
import argparse,io,json,time,uuid,urllib.request,zipfile
from pathlib import Path
from launch_live import memory_state
from validate_b_suite import call,BASE

CASES=[('congestion','merge'),('congestion','end_ride'),
       ('night','widen'),('night','pass'),('night','safe_stop'),
       ('fog','slow'),('fog','safe_stop'),('yield','creep'),('yield','end_ride'),
       ('carpool','support'),('carpool','end_ride'),('rattle','inspect'),('rattle','safe_stop'),
       ('cargo','inspect'),('cargo','avoid'),('cargo','stop'),('cargo','delegate'),('fog','inspect')]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start-at',type=int,default=0);ap.add_argument('--limit',type=int);args=ap.parse_args()
    if call('/state').get('kind')!='hongik-native-carla':raise RuntimeError('Native CARLA required')
    if call('/api/participant/current').get('participant'):raise RuntimeError('Participant registered; their session is left unchanged')
    folder=Path(__file__).resolve().parent/'validation'/('remaining-b-'+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir()
    results=[]
    for index,(profile,action) in list(enumerate(CASES))[args.start_at:args.start_at+args.limit if args.limit is not None else None]:
        if memory_state()<2:raise RuntimeError('Validation requires 2 GiB commit headroom')
        if call('/api/participant/current').get('participant'):raise RuntimeError('Participant took over')
        print(f'PREPARE {index} {profile}/{action}',flush=True)
        call('/api/select',dict(profile=profile,condition='B',presentation='midterm',language='ko'))
        start=time.monotonic()
        while True:
            state=call('/state')
            if state.get('error'):raise RuntimeError(state['error'])
            if state.get('phase')=='live' and state.get('profile')==profile and state.get('frames',0)>3:break
            if time.monotonic()-start>120:raise RuntimeError('Setup timeout')
            time.sleep(.4)
        sid=state['scenario']['session'];navid=call('/api/state')['session']['navigation']['id']
        row=dict(index=index,profile=profile,action=action,passed=False);samples=[];sent=False;view=False;phase=None
        def command(name,details=None):
            reply=call('/api/command',dict(session_id=sid,navigation_id=navid,request_id=uuid.uuid4().hex,action=name,
                client_event={'source':'unregistered developer remaining-action validation',**(details or {})}))
            for _ in range(60):
                answer=call('/api/reply?session='+sid+'&id='+reply['command_id'])
                if answer.get('accepted') is False:raise RuntimeError(answer.get('message'))
                if answer.get('accepted') is True:return
                time.sleep(.1)
            raise RuntimeError('Command reply timeout')
        try:
            call('/control',dict(mode='auto',session_id=sid));start=time.monotonic()
            while time.monotonic()-start<230:
                if memory_state()<2:raise RuntimeError('Validation headroom below 2 GiB')
                if call('/api/participant/current').get('participant'):raise RuntimeError('Participant took over')
                state=call('/state');sc=state['scenario'];study=sc['study']
                if sc['session']!=sid:raise RuntimeError('Session changed')
                if state.get('error'):raise RuntimeError(state['error'])
                samples.append(dict(state=state))
                if sc.get('collision_count',0):raise RuntimeError('Physical ego collision')
                if sc['onset'] and not sent:
                    command('study_open',{'options_visible':True});command('study_choice',{'choice':'study_'+action});command('study_'+action);sent=True
                if study['action']=='inspect' and study['phase'] in ('applying','observing') and not view:
                    command('study_view_opened',{'surface':'developer state validation; not gaze or browser inspection'});view=True
                if study['phase']!=phase:
                    phase=study['phase'];print(f'{index} {profile}/{action} {phase}',flush=True)
                if sc['completed']:break
                time.sleep(.4)
            row.update(completed=sc['completed'],status=sc['outcome']['status'],summary=sc['outcome']['summary'],
                       elapsed_s=sc['elapsed_s'],speed_kph=state['speed_kph'],collisions=sc.get('collision_count',0),service_end=study['service_end'])
            if not sc['completed'] or state['speed_kph']>=.5:raise RuntimeError('Not completed and physically stopped')
            if action=='end_ride' and row['status']=='achieved' and not study['service_end']:raise RuntimeError('Missing verified service end')
            allowed={'partial'} if action=='support' else {'achieved','partial'}
            if profile=='carpool' and action=='end_ride':allowed={'achieved'}
            if profile=='congestion' and action=='merge':allowed|={'unfulfilled'}
            if row['status'] not in allowed:raise RuntimeError('Unexpected outcome '+str(row['status']))
            with urllib.request.urlopen(BASE+'/rig/bundle?after=-1',timeout=10) as response:bundle=response.read()
            with zipfile.ZipFile(io.BytesIO(bundle)) as z:(folder/f'{index}-{profile}-{action}.jpg').write_bytes(z.read('center.jpg'))
            row['passed']=True
        except Exception as exc:
            row['error']=str(exc)
        finally:
            results.append(row)
            (folder/f'{index}-samples.json').write_text(json.dumps(samples,ensure_ascii=False),'utf-8')
            (folder/'results.json').write_text(json.dumps(dict(scope='Actual local CARLA; API outcomes only; no participant, iPad, audio playback or physical motion claim',results=results),ensure_ascii=False,indent=2),'utf-8')
            current=call('/state')
            if not call('/api/participant/current').get('participant') and (current.get('scenario') or {}).get('session')==sid and not current['scenario']['completed']:
                call('/control',dict(mode='paused',session_id=sid))
        print('RESULT '+json.dumps(row,ensure_ascii=False),flush=True)
        if not row['passed']:raise RuntimeError('Failed; evidence: '+str(folder))
    print('REMAINING CHECKS COMPLETE '+str(folder),flush=True)

if __name__=='__main__':main()
