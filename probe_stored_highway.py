"""Rebuild a stored initial highway request from its private actor/camera record."""
import argparse,sys,json,time,uuid,io
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import grpc,numpy as np
from PIL import Image
from nre.grpc.protos import sensorsim_pb2 as p
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scene_bridge import Scene,TRIAL,grpc_pose
from highway_blockade import HighwayBlockade

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--label',required=True);args=ap.parse_args()
    row=json.loads((args.run/'first-live-frame.json').read_text());ready=json.loads((args.run/'carla-ready.json').read_text());scene=Scene('congestion')
    if row['scenario']['elapsed_s']!=0 or ready['scene_id']!=scene.scene_id:raise RuntimeError('Use a paused initial highway frame')
    cfg=json.loads((TRIAL/'reports/wide-highway-v2-config.json').read_text(encoding='utf-8-sig'))
    stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)]))
    catalog=stub.get_dynamic_objects(p.AvailableDynamicObjectsRequest(scene_id=scene.scene_id),timeout=30)
    for actor in catalog.dynamic_objects:
        if actor.id in cfg['vehicles']:
            d=actor.object_size;cfg['vehicles'][actor.id]['size']=[d.size_x,d.size_y,d.size_z]
    folder=ROOT/'validation'/('highway-stored-reference-'+uuid.uuid4().hex[:8]);folder.mkdir()
    sc=HighwayBlockade(scene.route,folder/'probe-events.jsonl',cfg)
    matrices={}
    for spec in row['scenario']['traffic']:
        track=spec['track_id'];size=cfg['vehicles'][track]['size'];station=spec['s'];clipped=float(np.clip(station,0,sc.route.length))
        lateral=(2-spec['lane'])*sc.LANE_WIDTH
        mat=sc.route.sample(clipped,lateral,height=size[2]/2)
        mat[:3,3]+=mat[:3,0]*(station-clipped);matrices[track]=mat
    matrices[sc.TRACK_ID]=np.array(row['scenario_cuboid_pose']);sc.events.close()
    stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)]))
    cam=next(c for c in stub.get_available_cameras(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=15).available_cameras if c.logical_id==scene.camera_id)
    objects=[]
    for track in row['dynamic_actor_ids']:
        pose=grpc_pose(scene.inverse_alignment@matrices[track]);objects.append(p.DynamicObject(track_id=track,pose_pair=p.PosePair(start_pose=pose,end_pose=pose)))
    eye=grpc_pose(np.array(row['camera_pose']));w,h=row['dimensions'];ts=row['scene_timestamp_us']
    req=p.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=w,resolution_h=h,camera_intrinsics=cam.intrinsics,
        frame_start_us=ts,frame_end_us=ts+1,sensor_pose=p.PosePair(start_pose=eye,end_pose=eye),dynamic_objects=objects,image_format=p.ImageFormat.JPEG,image_quality=95)
    response=stub.render_rgb(req,timeout=90);(folder/'new.jpg').write_bytes(response.image_bytes);(folder/'request.pb').write_bytes(req.SerializeToString())
    original=(args.run/'first-live-frame.jpg').read_bytes();a=np.asarray(Image.open(io.BytesIO(original)),dtype=np.float32);b=np.asarray(Image.open(io.BytesIO(response.image_bytes)),dtype=np.float32);diff=np.abs(a-b)
    result=dict(label=args.label,actual_nurec_render=True,reference=str(args.run),reconstructed_from_stored_pose_record=True,
        jpeg_bytes_identical=original==response.image_bytes,mean_absolute=float(diff.mean()),max_absolute=float(diff.max()),actor_count=len(objects))
    (folder/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(folder=str(folder),result=result)),flush=True)

if __name__=='__main__':main()
