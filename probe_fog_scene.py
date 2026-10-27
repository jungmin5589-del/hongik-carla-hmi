"""Private fixed-request source comparison; never changes the driving trial."""
import json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import grpc,numpy as np
from scipy.spatial.transform import Rotation,Slerp
from nre.grpc.protos import sensorsim_pb2 as p
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scene_bridge import Scene,grpc_pose

def main():
    scene=Scene('fog');run=ROOT/'runs/20261027-235957'
    rows=[json.loads(s) for s in (run/'frames.jsonl').read_text().splitlines()]
    row=min((r for r in rows if r['scenario']['elapsed_s']>0),key=lambda r:abs(r['scenario']['elapsed_s']-10.))
    folder=ROOT/'validation'/('fog-source-comparison-'+uuid.uuid4().hex[:8]);folder.mkdir()
    stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)]))
    cam=next(v for v in stub.get_available_cameras(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=30).available_cameras if v.logical_id==scene.camera_id)
    catalog=stub.get_dynamic_objects(p.AvailableDynamicObjectsRequest(scene_id=scene.scene_id),timeout=30)
    editable={v.id for v in catalog.dynamic_objects};stamp=row['scene_timestamp_us'];objects=[];near=[]
    eye=np.array(row['camera_pose']);data=scene.tracks['tracks_data']
    for i,track in enumerate(data['tracks_id']):
        if str(track) not in editable:continue
        poses=np.array(data['tracks_poses'][i]);ts=np.array(data['tracks_timestamps_us'][i])
        if not ts[0]<=stamp<=ts[-1] or len(ts)<2:continue
        k=min(max(int(np.searchsorted(ts,stamp))-1,0),len(ts)-2);u=float(np.clip((stamp-ts[k])/max(ts[k+1]-ts[k],1),0,1))
        mat=np.eye(4);mat[:3,3]=(1-u)*poses[k,:3]+u*poses[k+1,:3]
        mat[:3,:3]=Slerp([0,1],Rotation.from_quat(poses[k:k+2,3:]))([u]).as_matrix()[0]
        pose=grpc_pose(mat);objects.append(p.DynamicObject(track_id=str(track),pose_pair=p.PosePair(start_pose=pose,end_pose=pose)))
        relative=(mat[:3,3]-eye[:3,3])@eye[:3,:3]
        near.append(dict(id=str(track),distance=float(np.linalg.norm(relative)),camera_relative=relative.tolist()))
    lead_id=row['scenario']['id'];lead_track=next(iter(row['dynamic_actor_ids']))
    lead_pose=grpc_pose(scene.inverse_alignment@np.array(row['scenario_cuboid_pose']))
    lead=p.DynamicObject(track_id=lead_track,pose_pair=p.PosePair(start_pose=lead_pose,end_pose=lead_pose))
    original=scene.poses[row['route_index']]@scene.camera_mount
    for label,camera,dynamic in [('trial-lead-only',eye,[lead]),('trial-native-traffic',eye,objects),('recorded-camera-native-traffic',original,objects)]:
        pose=grpc_pose(camera)
        req=p.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=1280,resolution_h=720,camera_intrinsics=cam.intrinsics,
            frame_start_us=stamp,frame_end_us=stamp+1,sensor_pose=p.PosePair(start_pose=pose,end_pose=pose),dynamic_objects=dynamic,image_format=p.ImageFormat.JPEG,image_quality=95)
        response=stub.render_rgb(req,timeout=120);(folder/(label+'.jpg')).write_bytes(response.image_bytes)
    summary=dict(actual_nurec_render=True,actual_live_trial=False,elapsed_s=row['scenario']['elapsed_s'],lead_track=lead_track,
        camera_translation_difference_m=float(np.linalg.norm(eye[:3,3]-original[:3,3])),
        nearest=sorted(near,key=lambda v:v['distance'])[:12],available_cameras=[v.logical_id for v in stub.get_available_cameras(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=30).available_cameras])
    (folder/'result.json').write_text(json.dumps(summary,indent=2));print(json.dumps(dict(folder=str(folder),result=summary)),flush=True)

if __name__=='__main__':main()
