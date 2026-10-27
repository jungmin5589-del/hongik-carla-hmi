"""Inspect same-frame native range without changing the visible live trial."""
import json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import grpc,numpy as np
from scipy.spatial.transform import Rotation,Slerp
from nre.grpc.protos import sensorsim_pb2 as p
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scene_bridge import Scene,grpc_pose
from fog_effect import FogEffect
from range_transport import decode_range_hint

def main():
    run=max((ROOT/'runs').iterdir(),key=lambda p:p.name);scene=Scene('fog')
    rows=[json.loads(s) for s in (run/'frames.jsonl').read_text().splitlines()]
    row=min((r for r in rows if r['scenario']['elapsed_s']>0),key=lambda r:abs(r['scenario']['elapsed_s']-65.))
    folder=ROOT/'validation'/('fog-depth-'+uuid.uuid4().hex[:8]);folder.mkdir()
    stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024),('grpc.max_metadata_size',128*1024)]))
    cam=next(v for v in stub.get_available_cameras(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=30).available_cameras if v.logical_id==scene.camera_id)
    stamp=row['scene_timestamp_us'];objects=[];data=scene.tracks['tracks_data']
    for track in row['dynamic_actor_ids']:
        if track=='6':mat=scene.inverse_alignment@np.array(row['scenario_cuboid_pose'])
        else:
            i=data['tracks_id'].index(track);poses=np.array(data['tracks_poses'][i]);ts=np.array(data['tracks_timestamps_us'][i]);k=min(max(int(np.searchsorted(ts,stamp))-1,0),len(ts)-2);u=float(np.clip((stamp-ts[k])/max(ts[k+1]-ts[k],1),0,1))
            mat=np.eye(4);mat[:3,3]=(1-u)*poses[k,:3]+u*poses[k+1,:3];mat[:3,:3]=Slerp([0,1],Rotation.from_quat(poses[k:k+2,3:]))([u]).as_matrix()[0]
        pose=grpc_pose(mat);objects.append(p.DynamicObject(track_id=track,pose_pair=p.PosePair(start_pose=pose,end_pose=pose)))
    eye=grpc_pose(np.array(row['camera_pose']))
    req=p.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=1280,resolution_h=720,camera_intrinsics=cam.intrinsics,
        frame_start_us=stamp,frame_end_us=stamp+1,sensor_pose=p.PosePair(start_pose=eye,end_pose=eye),dynamic_objects=objects,image_format=p.ImageFormat.JPEG,image_quality=95)
    response,call=stub.render_rgb.with_call(req,timeout=90,metadata=(('x-nurec-range','1'),))
    hint=next(v.value for v in call.trailing_metadata() if v.key=='nurec-range-bin');ranges=decode_range_hint(hint,stamp)
    effect=FogEffect();effect.configure(cam.intrinsics);dirs=effect.rays;h,w=ranges.shape;report=[]
    for low,high in [(7/8,1),(3/4,7/8),(2/3,7/8),(.7,.95)]:
        block=ranges[int(h*low):int(h*high),w//4:w*3//4];valid=(block>.5)&(block<30)
        points=(dirs*ranges[...,None])[int(h*low):int(h*high),w//4:w*3//4][valid]
        row_stats=dict(y=[low,high],valid=int(valid.sum()),total=int(valid.size),minimum=float(block.min()),median=float(np.median(block)))
        if len(points)>4:
            coeff=np.linalg.lstsq(np.column_stack((points[:,[0,2]],np.ones(len(points)))),points[:,1],rcond=None)[0];row_stats['camera_plane_xz_to_y']=coeff.tolist()
        report.append(row_stats)
    np.savez_compressed(folder/'ranges.npz',ranges=ranges,rays=dirs);(folder/'clear.jpg').write_bytes(response.image_bytes)
    (folder/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(folder=str(folder),stats=report)))

if __name__=='__main__':main()
