"""Private asset-view check, using only existing authorized reconstructed actors."""
import time
from pathlib import Path
import grpc
from scene_bridge import Scene, grpc_pose, proto, SensorsimServiceStub
from scenario2 import Route

s=Scene();route=Route(s.route)
out=Path(__file__).resolve().parent/'validation'/('lead-candidates-'+time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True)
stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)]))
catalog=stub.get_dynamic_objects(proto.AvailableDynamicObjectsRequest(scene_id=s.scene_id),timeout=20)
camera=next(c for c in stub.get_available_cameras(proto.AvailableCamerasRequest(scene_id=s.scene_id),timeout=20).available_cameras if c.logical_id==s.camera_id)
sensor=grpc_pose(s.poses[0]@s.camera_mount)
for track_id in ['108','111','107','164']:
    lead=next(o for o in catalog.dynamic_objects if o.id==track_id)
    pose=grpc_pose(s.inverse_alignment@route.sample(20.,0.,0.,lead.object_size.size_z/2))
    obj=proto.DynamicObject(track_id=track_id,pose_pair=proto.PosePair(start_pose=pose,end_pose=pose))
    req=proto.RGBRenderRequest(scene_id=s.scene_id,resolution_w=1280,resolution_h=720,camera_intrinsics=camera.intrinsics,
        frame_start_us=s.start_us,frame_end_us=s.start_us+1,sensor_pose=proto.PosePair(start_pose=sensor,end_pose=sensor),
        dynamic_objects=[obj],image_format=proto.ImageFormat.JPEG,image_quality=95)
    (out/(track_id+'.jpg')).write_bytes(stub.render_rgb(req,timeout=30).image_bytes)
print(out,flush=True)
