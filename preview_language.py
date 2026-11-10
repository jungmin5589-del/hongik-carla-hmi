"""Isolated rendering fixture, never connects to a CARLA world or drives a car."""
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from native_carla import handler
from midterm_study import COPY,OPTIONS,option
import tempfile
from pathlib import Path
from research_store import ResearchStore

def fixture():
    title,situation,behavior=COPY['night'];sid='english-render-fixture'
    event=dict(active=True,pending=False,title=title,description=situation+' '+behavior,situation=situation,vehicle_action=behavior,
        live_detail='현재 속도 30 km/h · 앞차 간격 약 7 m',options=OPTIONS['night']+[option('maintain','그냥 둘게요','현재 차량의 대응을 유지해요.')],
        narration=dict(cached=True,url='/api/narration/audio/night.wav'),outcome=dict(phase='idle',summary=''),feedback='',staged_options=False,condition='B',
        study=dict(phase='idle',action=None,cancellable=False,repeatable=False))
    sc=dict(session=sid,id='drowsy_night',onset=True,completed=False,elapsed_s=12,horn_count=0,high_beam=dict(on=False),outcome=dict(phase='idle'),layout='two_lane_boundary_weaving',study=event['study'])
    points=lambda off:[dict(forward_m=f,right_m=off,width_m=3.5,yaw_deg=0) for f in range(-20,101,5)]
    return dict(connected=True,schema=2,frame=1,map='CARLA Town04',lane_width_m=3.5,
        ego=dict(id=1,forward_m=0,right_m=0,up_m=-.4,yaw_deg=0,speed_kmh=30,lane_index=2,lane_count=4),
        road=dict(id=1,lanes=[dict(id=i,points=points((i-1)*3.5)) for i in range(4)]),
        actors=[dict(id=2,kind='vehicle',role='lead',label='앞차',forward_m=12,right_m=1.5,up_m=-.4,yaw_deg=0,width_m=1.8,length_m=4.4,speed_kmh=30)],
        destinations=[],world_pose=dict(x=0,y=0,yaw=0),route=dict(points=[[0,0],[0,500]],index=0,remaining_m=500,destination=dict(name='목적지',point=[0,500]),arrived=False),
        session=dict(session_id=sid,stage='running',navigation=dict(id=sid+'-weaving',map_label='야간 주행',title=title,body=situation,research_event=event)),
        nurec=dict(phase='live',mode='auto',quality='high',speed_kph=30,scenario=sc),passive=dict(title=title,body=behavior))

def main():
    import native_carla
    native_carla.PORT=8784
    value=fixture()
    temporary=tempfile.TemporaryDirectory();research=ResearchStore(Path(temporary.name),start_worker=False);research.participant('QA-UI')
    bridge=SimpleNamespace(presentation='midterm',navigation=SimpleNamespace(state=lambda:value,atlas=lambda:dict(map='CARLA',roads=[],destinations=[],buildings=[]),
        command=lambda body:dict(session_id='english-render-fixture',command_id='fixture'),reply=lambda *args:dict(accepted=True,message='확인했습니다.')),
        state=dict(phase='choose'),scenario=None,research=research)
    print('Isolated English rendering fixture: 8784; not a driving session',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8784),handler(bridge)).serve_forever()

if __name__=='__main__':main()
