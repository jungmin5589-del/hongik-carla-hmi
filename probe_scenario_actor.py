"""Private visual check: same camera/time, explicit neural car pose edits."""
import json
import time
from pathlib import Path
import grpc
from scene_bridge import Scene, grpc_pose, proto, common, SensorsimServiceStub
from scenario2 import Route, Scenario2

root=Path(__file__).resolve().parent
out=root/'validation'/('scenario-actor-'+time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True)
s=Scene(); route=Route(s.route)
channel=grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)])
print('Waiting for actor-edit renderer',out,flush=True)
grpc.channel_ready_future(channel).result(timeout=600)
stub=SensorsimServiceStub(channel)
catalog=stub.get_dynamic_objects(proto.AvailableDynamicObjectsRequest(scene_id=s.scene_id),timeout=300)
lead=next(o for o in catalog.dynamic_objects if o.id==Scenario2.TRACK_ID)
camera=next(c for c in stub.get_available_cameras(proto.AvailableCamerasRequest(scene_id=s.scene_id),timeout=300).available_cameras if c.logical_id==s.camera_id)
sensor=grpc_pose(s.poses[0]@s.camera_mount)
results=[]
for name,lateral in [('empty',None),('centre',0.),('left',1.2),('right',-1.2)]:
    objects=[]
    if lateral is not None:
        matrix=s.inverse_alignment@route.sample(25.,lateral,0.,lead.object_size.size_z/2)
        pose=grpc_pose(matrix)
        objects=[proto.DynamicObject(track_id=Scenario2.TRACK_ID,pose_pair=proto.PosePair(start_pose=pose,end_pose=pose))]
    req=proto.RGBRenderRequest(scene_id=s.scene_id,resolution_w=1280,resolution_h=720,
        camera_intrinsics=camera.intrinsics,frame_start_us=s.start_us,frame_end_us=s.start_us+1,
        sensor_pose=proto.PosePair(start_pose=sensor,end_pose=sensor),dynamic_objects=objects,
        image_format=proto.ImageFormat.JPEG,image_quality=95)
    started=time.monotonic();response=stub.render_rgb(req,timeout=300)
    (out/(name+'.jpg')).write_bytes(response.image_bytes)
    results.append(dict(name=name,lateral_m=lateral,rpc_seconds=time.monotonic()-started))
    print(name,'rendered',flush=True)
(out/'result.json').write_text(json.dumps(dict(config=dict(stub.get_server_config(common.Empty(),timeout=20).server_config),results=results),indent=2))
print(out,flush=True)
