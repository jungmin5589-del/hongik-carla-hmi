"""Measure newly rendered live frames, not display refreshes or MP4 frame rate."""
import argparse
import json
import statistics
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from launch_live import memory_state

ROOT = Path(__file__).resolve().parent


def call(path, body=None):
    request = urllib.request.Request('http://127.0.0.1:8774' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'} if body is not None else {})
    with urllib.request.urlopen(request, timeout=5) as response:
        data=response.read()
        return json.loads(data) if data else None


def require_memory():
    available=memory_state()
    if available < 2.:
        subprocess.run([sys.executable,str(ROOT/'stop_live.py')],cwd=ROOT,
            timeout=45,creationflags=0x08000000,check=False)
        raise RuntimeError(f'Benchmark stopped safely: only {available:.2f} GiB commit headroom remains.')


def percentile(values, fraction):
    return sorted(values)[round((len(values)-1)*fraction)] if values else None


def wait_ready(seconds=660):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        require_memory()
        try:
            state = call('/state')
        except OSError:
            time.sleep(1)
            continue
        if state.get('error'):
            raise RuntimeError(state['error'])
        if state.get('phase') == 'live' and state.get('frames', 0) >= 12:
            return state
        time.sleep(.5)
    raise RuntimeError('Timed out waiting for a warm live renderer.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=30.)
    parser.add_argument('--label', required=True)
    parser.add_argument('--quality',choices=['high','balanced'],default='high')
    args = parser.parse_args()
    folder = ROOT/'validation'/('fps30-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    print(json.dumps({'event':'waiting', 'label':args.label, 'folder':str(folder)}), flush=True)
    try:
        state = wait_ready()
        expected={'high':(1280,720),'balanced':(960,540)}[args.quality]
        call('/control',{'quality':args.quality})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            state=call('/state')
            if (state['width'],state['height'])==expected:break
            require_memory();time.sleep(.1)
        else:raise RuntimeError('Requested native render dimensions were not acknowledged.')
        call('/control', {'reset':True})
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            ready = call('/state')
            if ready['scenario']['session'] != state['scenario']['session'] and ready['mode']=='paused':
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Reset was not acknowledged.')
        run = max((ROOT/'runs').iterdir(), key=lambda p:p.name)
        call('/control', {'mode':'auto'})
        start=time.monotonic(); first=call('/state'); observations=[]
        print(json.dumps({'event':'measuring','label':args.label,'seconds':args.seconds}),flush=True)
        while time.monotonic()-start < args.seconds:
            require_memory()
            sample=call('/state')
            if sample.get('error'):
                raise RuntimeError(sample['error'])
            if sample['scenario']['session'] != ready['scenario']['session']:
                raise RuntimeError('Scenario changed during measurement.')
            observations.append({'time':time.monotonic(),'state':sample})
            time.sleep(.1)
        end=time.monotonic(); last=call('/state')
        call('/control', {'mode':'paused'})
        (folder/'observations.json').write_text(json.dumps(observations),encoding='utf-8')
        frames=[]
        with (run/'frames.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                try: row=json.loads(line)
                except ValueError: continue
                if start <= row['monotonic'] <= end:
                    frames.append(row)
        intervals=[(b['monotonic']-a['monotonic'])*1000 for a,b in zip(frames,frames[1:])]
        stage_keys=('prepare_ms','request_ms','rpc_ms','postprocess_ms','trace_ms','total_ms')
        timings={key:[row['state']['frame_timings_ms'][key] for row in observations
            if key in row['state'].get('frame_timings_ms',{})] for key in stage_keys}
        fps=(last['frames']-first['frames'])/(end-start)
        p95=percentile(intervals,.95); longest=max(intervals,default=0.)
        elapsed=last['scenario']['elapsed_s']-first['scenario']['elapsed_s']
        cross_track=max(row['state']['cross_track_m'] for row in observations)
        clock_ratio=elapsed/(end-start)
        motion_ok=bool(.95<=clock_ratio<=1.05 and cross_track<.5)
        cadence_ok=bool(fps>=29.5 and p95 is not None and p95<=50 and longest<=100)
        result=dict(label=args.label, actual_carla_nurec=True, interpolated_frames=False,
            renderer_backend=state['renderer_backend'], server_config=state.get('server_renderer_config'),
            proxy_update_mode=state.get('proxy_update_mode'), target_fps=state.get('target_fps'),
            resolution=[state['width'],state['height']], wall_s=end-start,
            quality=args.quality,
            renderer_fps=fps, frame_count=last['frames']-first['frames'],
            interval_p95_ms=p95, interval_max_ms=longest,
            stages_ms={key:dict(median=statistics.median(values),p95=percentile(values,.95))
                for key,values in timings.items() if values},
            max_cross_track_m=cross_track,
            scenario_elapsed_s=elapsed, simulation_clock_ratio=clock_ratio,
            source=state['scene_id'], short_test=args.seconds<300,
            fps30_short_gate=bool(cadence_ok and motion_ok),
            full_trial_gate=bool(args.seconds>=300 and cadence_ok and motion_ok),
            limits='Single laptop, single camera; not a three-screen or participant study.')
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        with urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg',timeout=5) as response:
            (folder/'last-frame.jpg').write_bytes(response.read())
        print(json.dumps(result),flush=True)
    except Exception:
        import traceback
        (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        try: call('/control', {'mode':'paused'})
        except OSError: pass


if __name__ == '__main__':
    main()
