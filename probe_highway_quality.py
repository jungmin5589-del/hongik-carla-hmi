"""Repeat identical private highway RGB requests across inference-only changes."""
import argparse,json,time,uuid,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import grpc,numpy as np
from nre.grpc.protos import sensorsim_pb2 as p
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scene_bridge import Scene,grpc_pose,TRIAL
from highway_blockade import HighwayBlockade

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reference',type=Path);ap.add_argument('--label',required=True);args=ap.parse_args()
    folder=ROOT/'validation'/('highway-identical-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);folder.mkdir()
    stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)]))
    if args.reference:
        requests=[p.RGBRenderRequest.FromString(file.read_bytes()) for file in sorted(args.reference.glob('*.pb'))]
        if len(requests)!=3:raise RuntimeError('Expected three private reference requests')
    else:
        scene=Scene('congestion');config=json.loads((TRIAL/'reports/wide-highway-v2-config.json').read_text(encoding='utf-8-sig'))
        camera=next(c for c in stub.get_available_cameras(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=15).available_cameras if c.logical_id==scene.camera_id)
        scenario=HighwayBlockade(scene.route,folder/'probe-events.jsonl',config);requests=[]
        for index,(station,seconds) in enumerate([(0.,0.),(80.,20.),(180.,40.)]):
            station=min(station,scenario.route.length-50.)
            scenario.elapsed=seconds;scenario.ego_s=station;scenario.lead_s=station+18.;scenario.large_s=[scenario.lead_s+v for v in scenario.LARGE_OFFSETS]
            rig=scenario.route.sample(station,height=0.);eye=grpc_pose(scene.inverse_alignment@rig@scene.camera_mount)
            dynamic=[]
            for track,pose in scenario.traffic_poses().items():
                position=grpc_pose(scene.inverse_alignment@pose)
                dynamic.append(p.DynamicObject(track_id=track,pose_pair=p.PosePair(start_pose=position,end_pose=position)))
            ri=int(np.argmin(np.linalg.norm(scene.route[:,:2,3]-rig[:2,3],axis=1)))
            timestamp=int(scene.timestamps[ri])
            requests.append(p.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=1280,resolution_h=720,camera_intrinsics=camera.intrinsics,
                frame_start_us=timestamp,frame_end_us=timestamp+1,sensor_pose=p.PosePair(start_pose=eye,end_pose=eye),
                dynamic_objects=dynamic,image_format=p.ImageFormat.JPEG,image_quality=95))
        scenario.events.close()
    result=[]
    for index,request in enumerate(requests):
        (folder/(str(index)+'.pb')).write_bytes(request.SerializeToString())
        started=time.perf_counter();response=stub.render_rgb(request,timeout=90)
        data=response.image_bytes;(folder/(str(index)+'.jpg')).write_bytes(data)
        row=dict(index=index,rpc_ms=(time.perf_counter()-started)*1000,actor_count=len(request.dynamic_objects))
        if args.reference:
            from PIL import Image
            import io
            original=(args.reference/(str(index)+'.jpg')).read_bytes()
            a=np.asarray(Image.open(io.BytesIO(original)),dtype=np.float32);b=np.asarray(Image.open(io.BytesIO(data)),dtype=np.float32)
            diff=np.abs(a-b);row.update(jpeg_bytes_identical=original==data,mean_absolute=float(diff.mean()),max_absolute=float(diff.max()))
        result.append(row)
    (folder/'result.json').write_text(json.dumps(dict(label=args.label,actual_live_drive=False,actual_nurec_render=True,fixed_requests=True,reference=str(args.reference) if args.reference else None,results=result),indent=2))
    print(json.dumps(dict(folder=str(folder),results=result)),flush=True)

if __name__=='__main__':main()
