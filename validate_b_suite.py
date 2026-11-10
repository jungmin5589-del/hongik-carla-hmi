"""Actual owned CARLA B smoke run; no participant registration or motion output."""
import io,json,time,urllib.request,uuid,zipfile
from pathlib import Path
from launch_live import memory_state

BASE='http://127.0.0.1:8774'
CASES=[('congestion','study_horn'),('fog','study_inspect'),('night','study_horn'),('yield','study_announce'),('carpool','study_relocate'),('rattle','study_slow')]

def call(path,body=None):
    request=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)

def main():
    if call('/state').get('kind')!='hongik-native-carla':raise RuntimeError('Native CARLA required')
    if call('/api/participant/current').get('participant'):raise RuntimeError('Participant registered; leave their session untouched')
    folder=Path(__file__).resolve().parent/'validation'/('b-six-scenes-'+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir(exist_ok=False)
    results=[]
    for profile,action in CASES:
        if memory_state()<2:raise RuntimeError('Validation requires 2 GiB commit headroom')
        if call('/api/participant/current').get('participant'):raise RuntimeError('Participant took over; stop automatic validation')
        print('PREPARING '+profile,flush=True);call('/api/select',dict(profile=profile,condition='B',presentation='midterm',language='ko'))
        start=time.monotonic()
        while True:
            state=call('/state')
            if state.get('error'):raise RuntimeError(state['error'])
            if state.get('phase')=='live' and state.get('profile')==profile and state.get('frames',0)>3:break
            if time.monotonic()-start>110:raise RuntimeError('Setup timeout: '+profile)
            time.sleep(.5)
        sid=state['scenario']['session'];nav=call('/api/state');navid=nav['session']['navigation']['id']
        def command(name,details=None):
            reply=call('/api/command',dict(session_id=sid,navigation_id=navid,request_id=uuid.uuid4().hex,action=name,client_event={'source':'developer B suite; not participant research',**(details or {})}))
            for _ in range(50):
                answer=call('/api/reply?session='+sid+'&id='+reply['command_id'])
                if answer.get('accepted') is False:raise RuntimeError(answer.get('message'))
                if answer.get('accepted') is True:return
                time.sleep(.1)
            raise RuntimeError('Command response timeout')
        call('/control',dict(mode='auto',session_id=sid));sent=False;view=False;cancelled=False;start=time.monotonic();phases=set()
        try:
            while time.monotonic()-start<180:
                if memory_state()<2:raise RuntimeError('Validation headroom below 2 GiB')
                if call('/api/participant/current').get('participant'):raise RuntimeError('Participant took over')
                state=call('/state');sc=state['scenario'];study=sc['study']
                if sc['session']!=sid:raise RuntimeError('Session changed during validation')
                if state.get('error'):raise RuntimeError(state['error'])
                if sc.get('collision_count',0):raise RuntimeError('Physical collision: '+profile)
                if sc['onset'] and not sent:
                    command('study_open',{'options_visible':True});command('study_choice',{'choice':action});command(action);sent=True
                if study['action']=='inspect' and study['phase'] in ('applying','observing') and not view:
                    command('study_view_opened',{'surface':'developer state validation; not gaze'});view=True
                if profile=='fog' and study['phase']=='observing' and sc['elapsed_s']>=18 and not cancelled:
                    command('study_cancel_pending');call('/control',dict(mode='paused',session_id=sid));cancelled=True
                if study['phase'] not in phases:
                    phases.add(study['phase']);print(profile+' '+study['phase'],flush=True)
                if sc['completed']:break
                time.sleep(.4)
            if not sc['completed']:raise RuntimeError('Completion timeout: '+profile)
            if state['speed_kph']>=.5:raise RuntimeError('Not physically stopped')
            expected='cancelled' if profile=='fog' else 'achieved'
            row=dict(profile=profile,action=action,status=sc['outcome']['status'],expected=expected,completed=sc['completed'],elapsed_s=sc['elapsed_s'],collisions=sc.get('collision_count',0),speed_kph=state['speed_kph'],lab_rig=state.get('lab_rig'),passed=sc['outcome']['status']==expected)
            if profile=='fog':row['paused_stop_regression']=cancelled and state['mode']=='paused'
            with urllib.request.urlopen(BASE+'/rig/bundle?after=-1',timeout=8) as response:bundle=response.read()
            with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                row['same_frame_views']=sorted(n for n in archive.namelist() if n.endswith('.jpg'))
                (folder/(profile+'-center.jpg')).write_bytes(archive.read('center.jpg'))
            results.append(row);(folder/'results.json').write_text(json.dumps(dict(scope='Actual local CARLA three-view preview; one representative action per scene; no physical lab or participant study',results=results),ensure_ascii=False,indent=2),'utf-8');print('RESULT '+json.dumps(row,ensure_ascii=False),flush=True)
        finally:
            s=call('/state')
            if not s.get('scenario',{}).get('completed'):call('/control',dict(mode='paused',session_id=sid))
    print('B SUITE COMPLETE '+str(folder),flush=True)
    if not all(r['passed'] for r in results):raise RuntimeError('One or more actions did not achieve the expected result')

if __name__=='__main__':main()
