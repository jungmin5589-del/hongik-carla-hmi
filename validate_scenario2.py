"""Finite development QA through the same local control endpoint as the viewer."""
import json
import math
import time
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parent
out=root/'validation'/('scenario-driving-'+time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True)

def state():
    return json.load(urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=10))

def command(**body):
    request=urllib.request.Request('http://127.0.0.1:8774/control',json.dumps(body).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=10) as response:
        raw=response.read()
        return json.loads(raw) if raw else None

def save_frame(name):
    (out/(name+'.jpg')).write_bytes(urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg').read())

samples=[]
command(scenario='drowsy_night')
time.sleep(1.5)
initial=state();assert initial['phase']=='live',initial
session=initial['scenario']['session']
command(mode='auto')
began=time.monotonic()
try:
    while True:
        sample=state();samples.append(sample)
        assert sample['phase']=='live' and not sample['error'],sample
        assert sample['scenario']['session']==session,'QA interrupted by another reset'
        t=sample['scenario']['elapsed_s']
        if t>=18:break
        assert time.monotonic()-began<90,'Driving clock did not advance within QA deadline'
        if t<5.5:assert not sample['scenario']['onset']
        if sample['scenario']['onset'] and not any(x.get('event')=='opened' for x in samples):
            assert not sample['scenario']['dialog_open']
            command(interaction='notification_exposed',session=session)
            command(interaction='open',session=session)
            command(interaction='horn',session=session)
            samples.append({'event':'opened'})
            save_frame('horn-feedback')
        time.sleep(.25)
    before=state()
    command(interaction='maintain',session=session)
    command(interaction='close',session=session)
    assert not state()['scenario']['dialog_open']
    command(interaction='open',session=session)
    command(interaction='widen',session=session)
    widen_started=state()['scenario']['elapsed_s']
    deadline=time.monotonic()+90
    while state()['scenario']['elapsed_s']-widen_started<14:
        sample=state();samples.append(sample)
        assert sample['scenario']['session']==session,'QA interrupted by another reset'
        assert time.monotonic()<deadline,'Gap QA did not advance within deadline'
        time.sleep(.25)
    after=state()
    command(mode='paused')
    time.sleep(2)
    save_frame('widened-gap')
    command(interaction='close',session=session)
    real=[s for s in samples if 'scenario' in s]
    lat=[s['scenario']['lateral_m'] for s in real if s['scenario']['elapsed_s']>12 and s['scenario']['elapsed_s']<18]
    result={'passed':False,'initial':initial,'before_widen':before,'after_widen':after,
        'gap_gain_m':after['scenario']['gap_m']-before['scenario']['gap_m'],
        'weave_lateral_span_m':max(lat)-min(lat), 'samples':samples,
        'checks':{'notification_voluntary':True,'horn_count':after['scenario']['horn_count']==1,
                  'gap_increases':after['scenario']['gap_m']>before['scenario']['gap_m']+8,
                  'target_gap':after['scenario']['target_gap_m']==30.,
                  'weaving':max(lat)-min(lat)>1.7,
                  'ego_moves':math.dist(initial['carla_position'],after['carla_position'])>50}}
    result['passed']=all(result['checks'].values())
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'out':str(out),'passed':result['passed'],'checks':result['checks'],
        'gap_before':before['scenario']['gap_m'],'gap_after':after['scenario']['gap_m']}),flush=True)
    assert result['passed']
finally:
    if not (out/'result.json').exists():
        (out/'incomplete-qa.json').write_text(json.dumps({'completed':False,'samples':samples},indent=2),encoding='utf-8')
    command(mode='paused')
