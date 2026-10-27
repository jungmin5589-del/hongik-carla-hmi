"""Private comparison of an independent lead and native roadside context."""
import json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import grpc,numpy as np
from scipy.spatial.transform import Rotation,Slerp
from nre.grpc.protos import sensorsim_pb2 as p
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scene_bridge import Scene,grpc_pose
from night_weaving import recorded_track_height
from scenario2 import Route as RouteProjection

def main():
    scene=Scene('fog');rows=[json.loads(s) for s in (ROOT/'runs/20261027-235957/frames.jsonl').read_text().splitlines()]
    row=min((r for r in rows if r['scenario']['elapsed_s']>0),key=lambda r:abs(r['scenario']['elapsed_s']-10.))
    folder=ROOT/'validation'/('fog-lead-context-'+uuid.uuid4().hex[:8]);folder.mkdir()
    stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)]))
    cam=next(v for v in stub.get_available_cameras(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=30).available_cameras if v.logical_id==scene.camera_id)
    catalog=stub.get_dynamic_objects(p.AvailableDynamicObjectsRequest(scene_id=scene.scene_id),timeout=30)
    stamp=row['scene_timestamp_us'];data=scene.tracks['tracks_data'];native={};heights={}
    for track in ['6','7','36']:
        i=data['tracks_id'].index(track);poses=np.array(data['tracks_poses'][i]);ts=np.array(data['tracks_timestamps_us'][i])
        k=min(max(int(np.searchsorted(ts,stamp))-1,0),len(ts)-2);u=float(np.clip((stamp-ts[k])/max(ts[k+1]-ts[k],1),0,1))
        mat=np.eye(4);mat[:3,3]=(1-u)*poses[k,:3]+u*poses[k+1,:3];mat[:3,:3]=Slerp([0,1],Rotation.from_quat(poses[k:k+2,3:]))([u]).as_matrix()[0]
        pose=grpc_pose(mat);native[track]=p.DynamicObject(track_id=track,pose_pair=p.PosePair(start_pose=pose,end_pose=pose))
        aligned=[]
        for v in poses:
            m=np.eye(4);m[:3,3]=v[:3];aligned.append(scene.alignment@m)
        if track=='6':heights[track]=recorded_track_height(RouteProjection(scene.route),aligned)
    lead=np.array(row['scenario_cuboid_pose']);ground=RouteProjection(scene.route).sample(row['scenario']['lead_s'],height=0.)
    lead[:3,3]=ground[:3,3]+np.array([0.,0.,heights['6']]);pose=grpc_pose(scene.inverse_alignment@lead)
    target=p.DynamicObject(track_id='6',pose_pair=p.PosePair(start_pose=pose,end_pose=pose));eye=grpc_pose(np.array(row['camera_pose']))
    request=p.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=1280,resolution_h=720,camera_intrinsics=cam.intrinsics,
        frame_start_us=stamp,frame_end_us=stamp+1,sensor_pose=p.PosePair(start_pose=eye,end_pose=eye),dynamic_objects=[target,native['7'],native['36']],image_format=p.ImageFormat.JPEG,image_quality=95)
    response=stub.render_rgb(request,timeout=90);(folder/'lead6-context7-36.jpg').write_bytes(response.image_bytes)
    (folder/'request.pb').write_bytes(request.SerializeToString())
    result=dict(heights=heights,objects=[dict(id=v.id,size=[v.object_size.size_x,v.object_size.size_y,v.object_size.size_z]) for v in catalog.dynamic_objects if v.id in native],actual_nurec_render=True,actual_live_trial=False)
    (folder/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(folder=str(folder),result=result)))

if __name__=='__main__':main()
