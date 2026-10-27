"""Check the stopped CARLA lead cuboid against the pose sent to NuRec."""
import json
import math
import time
import urllib.request
from pathlib import Path
import carla

root=Path(__file__).resolve().parent
state=json.load(urllib.request.urlopen('http://127.0.0.1:8774/state'))
assert state['phase']=='live' and state['mode']=='paused',state
client=carla.Client('127.0.0.1',2016)
world=client.get_world()
actor=next(a for a in world.get_actors() if a.attributes.get('role_name')=='nurec_track_108')
centre=actor.get_transform().transform(actor.bounding_box.location)
run=sorted((root/'runs').iterdir())[-1]
for _ in range(10):
    try:
        with (run/'frames.jsonl').open('rb') as f:
            f.seek(max(0,(run/'frames.jsonl').stat().st_size-32768))
            record=json.loads(f.read().splitlines()[-1])
        break
    except (ValueError,IndexError):
        time.sleep(.1)
expected=[row[3] for row in record['scenario_cuboid_pose'][:3]]
actual=[centre.x,-centre.y,centre.z]
error=math.dist(expected,actual)
result={'passed':error<.1 and '108' in record['dynamic_actor_ids'],
        'proxy_center_error_m':error,'carla_actor_id':actor.id,
        'actual_enu':actual,'requested_enu':expected,'render_frame_id':record['id'],
        'run':str(run),'method':'same frozen trial pose; source cuboid centre matched to CARLA bounding-box centre'}
out=root/'validation'/('scenario-proxy-'+time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True)
(out/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
assert result['passed']
