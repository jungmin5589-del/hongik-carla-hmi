"""Isolate JPEG encoding/transport from rendering, at one verified live pose."""
import argparse
import io
import json
import statistics
import sys
import time
import uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
import grpc
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation
from nre.grpc.protos import common_pb2 as common, sensorsim_pb2 as proto
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub


def pose(matrix):
    t=matrix[:3,3];q=Rotation.from_matrix(matrix[:3,:3]).as_quat()
    return common.Pose(vec=common.Vec3(x=t[0],y=t[1],z=t[2]),
        quat=common.Quat(x=q[0],y=q[1],z=q[2],w=q[3]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    ready=json.loads((args.run/'carla-ready.json').read_text(encoding='utf-8-sig'))
    row=json.loads((args.run/'first-live-frame.json').read_text(encoding='utf-8-sig'))
    if len(row['dynamic_actor_ids'])!=1:raise RuntimeError('Use the single-lead night trial for this isolated probe.')
    folder=ROOT/'validation'/('transport-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);folder.mkdir()
    stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',16*1024*1024)]))
    camera=next(c for c in stub.get_available_cameras(proto.AvailableCamerasRequest(scene_id=ready['scene_id'])).available_cameras
        if c.intrinsics.resolution_w>0)
    # Match the front camera actually used by the bridge, not source enumeration order.
    from scene_bridge import Scene
    scene=Scene('night')
    camera=next(c for c in stub.get_available_cameras(proto.AvailableCamerasRequest(scene_id=ready['scene_id'])).available_cameras
        if c.logical_id==scene.camera_id)
    lead=pose(np.linalg.inv(np.array(ready['alignment']))@np.array(row['scenario_cuboid_pose']))
    eye=pose(np.array(row['camera_pose']));width,height=row['dimensions']
    request=proto.RGBRenderRequest(scene_id=ready['scene_id'],resolution_w=width,resolution_h=height,
        camera_intrinsics=camera.intrinsics,frame_start_us=row['scene_timestamp_us'],frame_end_us=row['scene_timestamp_us']+1,
        sensor_pose=proto.PosePair(start_pose=eye,end_pose=eye),
        dynamic_objects=[proto.DynamicObject(track_id=row['dynamic_actor_ids'][0],pose_pair=proto.PosePair(start_pose=lead,end_pose=lead))],
        image_quality=95)
    results={}
    for kind,enum,native in [('jpeg_custom',proto.ImageFormat.JPEG,False),('jpeg_native',proto.ImageFormat.JPEG,True),
                             ('raw_native',proto.ImageFormat.RGB_UINT8_PLANAR,True)]:
        request.image_format=enum;rows=[]
        request.camera_intrinsics.CopyFrom(type(camera.intrinsics)(logical_id=camera.logical_id) if native else camera.intrinsics)
        for index in range(22):
            start=time.perf_counter();response=stub.render_rgb(request,timeout=60);rpc=(time.perf_counter()-start)*1000
            if kind.startswith('raw'):
                if len(response.image_bytes)!=width*height*3:raise RuntimeError('Unexpected raw RGB layout.')
                rgb=np.frombuffer(response.image_bytes,dtype=np.uint8).reshape(3,height,width).transpose(1,2,0)
                stream=io.BytesIO();Image.fromarray(rgb).save(stream,format='JPEG',quality=95);data=stream.getvalue()
            else:data=response.image_bytes
            total=(time.perf_counter()-start)*1000
            if index>=2:rows.append(dict(rpc_ms=rpc,total_ms=total,bytes=len(response.image_bytes)))
        (folder/(kind+'.jpg')).write_bytes(data)
        results[kind]=dict(median_rpc_ms=statistics.median(r['rpc_ms'] for r in rows),
            median_total_ms=statistics.median(r['total_ms'] for r in rows),samples=rows)
    (folder/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(dict(folder=str(folder),results=results)),flush=True)


if __name__=='__main__':main()
