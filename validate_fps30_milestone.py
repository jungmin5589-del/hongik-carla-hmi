"""Actual integration check of idle cadence, resume and retained HMI actions."""
import json
import time
import urllib.request
import uuid
from pathlib import Path
from benchmark_fps30 import call, wait_ready, require_memory
ROOT=Path(__file__).resolve().parent


def wait_for(predicate,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        require_memory();state=call('/state')
        if state.get('error'):raise RuntimeError(state['error'])
        if predicate(state):return state
        time.sleep(.1)
    raise RuntimeError('Actual integration check timed out.')


def main():
    folder=ROOT/'validation'/('fps30-milestone-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);folder.mkdir()
    print(json.dumps({'event':'waiting','folder':str(folder)}),flush=True)
    try:
        original=wait_ready()
        if original['renderer_backend']!='trained':raise RuntimeError('Restore the original renderer before this check.')
        call('/control',{'reset':True,'quality':'high'})
        ready=wait_for(lambda s:s['scenario']['session']!=original['scenario']['session'] and s['mode']=='paused'
            and s.get('render_cadence')=='idle',30)
        idle_start=time.monotonic();idle_frames=ready['frames'];time.sleep(3.2)
        idle=call('/state');idle_fps=(idle['frames']-idle_frames)/(time.monotonic()-idle_start)
        if not .5<idle_fps<1.6:raise RuntimeError('Idle renderer did not reduce its cadence.')
        start=time.monotonic();call('/control',{'mode':'auto'})
        resumed=wait_for(lambda s:s['mode']=='auto' and s['frames']>idle['frames'] and s.get('render_cadence')=='live',5)
        resume_s=time.monotonic()-start
        onset=wait_for(lambda s:s['scenario']['onset'],20)
        session=onset['scenario']['session']
        def command(action,details=None):
            return call('/api/command',dict(session_id=session,navigation_id=session+'-weaving',
                request_id=uuid.uuid4().hex,action=action,client_event=details or {}))
        command('study_open',{'options_visible':True})
        command('study_choice',{'choice':'study_distance'})
        command('study_distance')
        complete=wait_for(lambda s:s['scenario']['completed'],75)
        if complete['scenario']['action']!='widen' or not complete['scenario']['action_complete']:
            raise RuntimeError('The selected navigation action did not reach its result.')
        result=dict(actual_carla_nurec=True,actual_iphone=False,participant_study=False,renderer='trained',
            resolution=[complete['width'],complete['height']],idle_fps=idle_fps,resume_s=resume_s,
            retained_navigation_action='widen',completed=True,scenario=complete['scenario'],
            fps30_achieved=False,reason='Separate frame cadence benchmark remains below target.')
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
    except Exception:
        import traceback
        (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
    finally:
        try:call('/control',{'reset':True,'quality':'high','mode':'paused'})
        except (OSError,ValueError):pass
    final=wait_for(lambda s:s['mode']=='paused' and s['scenario']['elapsed_s']==0 and s.get('render_cadence')=='idle',15)
    with urllib.request.urlopen('http://127.0.0.1:8774/frame.jpg',timeout=5) as response:
        (folder/'ready-720p.jpg').write_bytes(response.read())
    print(json.dumps({'event':'ready','folder':str(folder),'renderer':final['renderer_backend']}),flush=True)


if __name__=='__main__':main()
