"""Private fixed-pose native-fog visual QA; separate from physical driving trials."""
import sys,json,time,uuid
from pathlib import Path
import grpc,numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
from nre.grpc.protos import sensorsim_pb2 as p
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scene_bridge import Scene,grpc_pose
from fog_trial import fog_at
run=max((ROOT/'runs').iterdir(),key=lambda x:x.name)
ready=json.loads((run/'carla-ready.json').read_text());row=json.loads((run/'first-live-frame.json').read_text())
scene=Scene('fog');stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024),('grpc.max_metadata_size',128*1024)]))
camera=next(c for c in stub.get_available_cameras(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=10).available_cameras if c.logical_id==scene.camera_id)
eye=grpc_pose(np.array(row['camera_pose']));lead=grpc_pose(np.linalg.inv(ready['alignment'])@np.array(row['scenario_cuboid_pose']))
request=p.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=1280,resolution_h=720,camera_intrinsics=camera.intrinsics,
    frame_start_us=row['scene_timestamp_us'],frame_end_us=row['scene_timestamp_us']+1,
    sensor_pose=p.PosePair(start_pose=eye,end_pose=eye),dynamic_objects=[p.DynamicObject(track_id=row['dynamic_actor_ids'][0],pose_pair=p.PosePair(start_pose=lead,end_pose=lead))],image_format=p.ImageFormat.JPEG,image_quality=95)
folder=ROOT/'validation'/('native-fog-visual-'+uuid.uuid4().hex[:8]);folder.mkdir();results=[]
for at in [0.,60.,180.,290.]:
    beta=fog_at(at)['beta'];metadata=() if beta==0 else (('x-nurec-range','1'),('x-nurec-fog',json.dumps([beta,at])))
    started=time.perf_counter();response,call=stub.render_rgb.with_call(request,timeout=45,metadata=metadata)
    applied=any(m.key=='nurec-fog' and m.value=='1' for m in call.trailing_metadata())
    assert applied==(beta>0)
    (folder/(str(int(at))+'.jpg')).write_bytes(response.image_bytes)
    results.append(dict(at_s=at,beta=beta,native_applied=applied,rpc_ms=(time.perf_counter()-started)*1000))
(folder/'result.json').write_text(json.dumps(dict(actual_gpu_render=True,actual_driving=False,fixed_pose=True,results=results),indent=2));print(folder)
