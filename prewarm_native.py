"""Warm only the owned NuRec renderer; no CARLA or live-driving claim."""
import io,json,time,uuid,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'vendor'))
import grpc,numpy as np
from PIL import Image
from nre.grpc.protos import sensorsim_pb2 as p
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scene_bridge import Scene,grpc_pose
from benchmark_fps30 import require_memory
from launch_live import memory_state,open_port

def wait_rpc(future):
    while not future.done():require_memory();time.sleep(.4)
    return future.result()

def main():
    if open_port(2016):raise RuntimeError('Stop only the owned CARLA before renderer-only prewarm')
    folder=ROOT/'validation'/('native-kernel-prewarm-'+uuid.uuid4().hex[:8]);folder.mkdir();minimum=memory_state()
    print(json.dumps(dict(event='waiting_renderer_only',folder=str(folder))),flush=True)
    scene=Scene('congestion');stub=SensorsimServiceStub(grpc.insecure_channel('127.0.0.1:46435',options=[('grpc.max_receive_message_length',32*1024*1024)]))
    deadline=time.monotonic()+660;camera=None
    while time.monotonic()<deadline:
        require_memory();minimum=min(minimum,memory_state())
        try:
            available=wait_rpc(stub.get_available_cameras.future(p.AvailableCamerasRequest(scene_id=scene.scene_id),timeout=6))
            camera=next(c for c in available.available_cameras if c.logical_id==scene.camera_id);break
        except grpc.RpcError:time.sleep(1)
    if camera is None:raise RuntimeError('Renderer-only prewarm did not become ready')
    pose=grpc_pose(scene.poses[0]@scene.camera_mount);ts=int(scene.timestamps[0])
    req=p.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=1280,resolution_h=720,camera_intrinsics=camera.intrinsics,
        frame_start_us=ts,frame_end_us=ts+1,sensor_pose=p.PosePair(start_pose=pose,end_pose=pose),
        image_format=p.ImageFormat.JPEG,image_quality=95)
    rows=[]
    for index in range(2):
        started=time.monotonic();future=stub.render_rgb.future(req,timeout=300)
        while not future.done():require_memory();minimum=min(minimum,memory_state());time.sleep(.4)
        data=future.result().image_bytes
        with Image.open(io.BytesIO(data)) as image:image.load();assert image.size==(1280,720)
        (folder/(str(index)+'.jpg')).write_bytes(data);rows.append(dict(index=index,wall_s=time.monotonic()-started))
        print(json.dumps(dict(event='rendered',index=index,wall_s=rows[-1]['wall_s'])),flush=True)
    out=dict(actual_nurec_render=True,carla_running=False,actual_live_driving=False,minimum_commit_headroom_gib=minimum,frames=rows)
    (folder/'result.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(folder=str(folder),result=out)),flush=True)

if __name__=='__main__':main()
