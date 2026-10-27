"""Short actual four-lane runtime comparison; private metrics stay on D."""
import argparse
import json
from pathlib import Path
import statistics
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parent


def request(base,path,body=None):
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'} if body is not None else {})
    with urllib.request.urlopen(req,timeout=5) as response:data=response.read()
    return json.loads(data) if data else None


def call(path,body=None):return request('http://127.0.0.1:8774',path,body)


def wait_for(predicate,seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        state=call('/state')
        if state.get('error'):raise RuntimeError(state['error'])
        if predicate(state):return state
        time.sleep(.15)
    raise RuntimeError('Timed out preparing the controlled comparison.')


def percentile(values,p):
    if not values:return None
    values=sorted(values);return values[round((len(values)-1)*p)]


def render_trace(run,begin,end,dimensions):
    with (run/'frames.jsonl').open('rb') as stream:
        stream.seek(0,2);stream.seek(max(0,stream.tell()-4_000_000));lines=stream.read().splitlines()
    frames=[]
    for line in lines:
        try:row=json.loads(line)
        except (ValueError,UnicodeError):continue
        if begin<=row['monotonic']<=end and row['dimensions']==list(dimensions):frames.append(row)
    times=[f['monotonic'] for f in frames]
    gaps=[(b-a)*1000 for a,b in zip(times,times[1:])]
    return dict(trace_frames=len(frames),rgb_interval_p95_ms=percentile(gaps,.95),
        rgb_interval_max_ms=max(gaps) if gaps else None,
        rpc_median_ms=statistics.median([f['rpc_ms'] for f in frames]) if frames else None)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--launch-id',required=True);args=parser.parse_args()
    deadline=time.monotonic()+660
    while time.monotonic()<deadline:
        hub=request('http://127.0.0.1:8775','/api/status')
        if hub['launch_id']!=args.launch_id:raise RuntimeError('The selected scenario changed.')
        if hub.get('error') or hub['phase']=='error' or hub['phase']=='failed':raise RuntimeError(str(hub))
        if hub['phase']=='ready':break
        time.sleep(1)
    else:raise RuntimeError('The four-lane scene did not become ready.')
    state=call('/state')
    if state.get('profile')!='congestion' or state['scenario'].get('layout')!='four_lane_blockade':
        raise RuntimeError('The four-lane experiment is not the active scene.')
    run=max((ROOT/'runs').iterdir(),key=lambda p:p.name)
    if json.loads((run/'carla-ready.json').read_text())['scene_id']!=state['scene_id']:
        raise RuntimeError('Trace source mismatch.')
    folder=ROOT/'validation'/('highway-720p-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    print(json.dumps(dict(event='benchmark_started',folder=str(folder))),flush=True)
    results=[]
    try:
        for quality,dimensions in [('high',(1280,720)),('balanced',(960,540))]:
            prior=call('/state')
            call('/control',{'quality':quality,'reset':True})
            ready=wait_for(lambda s:s['scenario']['session']!=prior['scenario']['session']
                and s['mode']=='paused' and (s['width'],s['height'])==dimensions
                and s['frames']>=prior['frames']+4,45)
            call('/control',{'mode':'auto'})
            start=time.monotonic();first=call('/state');rows=[]
            while time.monotonic()-start<22:
                current=call('/state')
                if current.get('error'):raise RuntimeError(current['error'])
                if current['scenario']['session']!=ready['scenario']['session']:raise RuntimeError('Trial reset during measurement.')
                rows.append(dict(time=time.monotonic(),state=current));time.sleep(.1)
            end=time.monotonic();last=call('/state');call('/control',{'mode':'paused'})
            (folder/(quality+'-observations.json')).write_text(json.dumps(rows),encoding='utf-8')
            result=dict(quality=quality,resolution=dimensions,wall_s=end-start,
                renderer_fps=(last['frames']-first['frames'])/(end-start),
                simulation_elapsed_s=last['scenario']['elapsed_s']-first['scenario']['elapsed_s'],
                final_speed_kph=last['speed_kph'],max_cross_track_m=max(r['state']['cross_track_m'] for r in rows),
                no_runtime_error=True,configured_fps_limit=10,**render_trace(run,start,end,dimensions))
            results.append(result);print(json.dumps(result),flush=True)
        report=dict(actual_carla_nurec=True,short_runtime_test=True,full_trial_or_lab_test=False,
            three_screens_tested=False,source=state['scene_id'],results=results,default_resolution=[1280,720],
            comparison_limits='Same route reset and traffic configuration; sequential warm runs, not a controlled hardware benchmark.')
        (folder/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    finally:
        try:call('/control',{'quality':'high','reset':True})
        except OSError:pass
    wait_for(lambda s:s['mode']=='paused' and s['scenario']['elapsed_s']==0 and (s['width'],s['height'])==(1280,720),45)
    with urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg',timeout=5) as response:
        (folder/'ready-720p.jpg').write_bytes(response.read())
    print(json.dumps(dict(event='benchmark_finished',folder=str(folder),ready_resolution=[1280,720])),flush=True)


if __name__=='__main__':main()
