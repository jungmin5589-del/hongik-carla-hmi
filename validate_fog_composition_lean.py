"""Compare full fog composition on an existing private source RGB/camera frame."""
from pathlib import Path
import json,time,uuid,statistics,importlib.util,io
import numpy as np
from PIL import Image
from fog_effect import FogEffect
from fog_trial import fog_at
ROOT=Path(__file__).resolve().parent
run=ROOT/'runs/20261020-212305'
old_path=ROOT/'backups/effect-workload-83cf7219b9fc4205843cb9267730d480/fog_effect.py'
spec=importlib.util.spec_from_file_location('previous_fog_effect',old_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=ROOT.parent
old=module.FogEffect();new=FogEffect()
row=json.loads((run/'first-live-frame.json').read_text());ready=json.loads((run/'carla-ready.json').read_text())
camera=np.array(row['camera_pose']);lead=np.linalg.inv(ready['alignment'])@row['scenario_cuboid_pose']
image=Image.open(run/'first-live-frame.jpg').convert('RGB').resize((1280,720));stream=io.BytesIO();image.save(stream,format='JPEG',quality=95);jpeg=stream.getvalue()
folder=ROOT/'validation'/('fog-composition-lean-'+uuid.uuid4().hex[:8]);folder.mkdir();results=[]
for at in [60.,180.,290.]:
    case=dict(fog=fog_at(at),elapsed_s=at);outputs={};timings={}
    for label,effect in [('previous',old),('lookup',new)]:
        samples=[]
        for i in range(7):
            started=time.perf_counter();data,meta=effect.apply(jpeg,camera,lead,case)
            if i:samples.append((time.perf_counter()-started)*1000)
        outputs[label]=np.array(Image.open(io.BytesIO(data)),dtype=np.int16);timings[label]=statistics.median(samples)
        (folder/(str(int(at))+'-'+label+'.jpg')).write_bytes(data)
    difference=np.abs(outputs['previous']-outputs['lookup'])
    results.append(dict(at_s=at,composite_median_ms=timings,mean_8bit_difference=float(difference.mean()),max_8bit_difference=int(difference.max())))
(folder/'result.json').write_text(json.dumps(dict(actual_live_render=False,input='existing private RGB/camera frame resampled to720p for equal CPU comparison',results=results),indent=2));print(json.dumps(dict(folder=str(folder),results=results)))
