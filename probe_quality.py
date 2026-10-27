"""Read-only resolution and actor-capability probe; never changes the live scene."""
import collections
import json
from pathlib import Path
import subprocess
import threading
import time
import grpc
from scene_bridge import Scene, grpc_pose, proto, SensorsimServiceStub

root = Path(__file__).resolve().parent
out = root / "validation" / ("quality-" + time.strftime("%Y%m%d-%H%M%S"))
out.mkdir(parents=True, exist_ok=False)
scene = Scene()
channel = grpc.insecure_channel("127.0.0.1:46435", options=[("grpc.max_receive_message_length", 32 * 1024 * 1024)])
stub = SensorsimServiceStub(channel)
cameras = stub.get_available_cameras(proto.AvailableCamerasRequest(scene_id=scene.scene_id), timeout=20)
camera = next(c for c in cameras.available_cameras if c.logical_id == scene.camera_id)
objects = stub.get_dynamic_objects(proto.AvailableDynamicObjectsRequest(scene_id=scene.scene_id), timeout=20)
capability = {"editable_actor_count":len(objects.dynamic_objects),
              "actor_classes":dict(collections.Counter(o.semantic_class for o in objects.dynamic_objects))}
pose = grpc_pose(scene.poses[0] @ scene.camera_mount)
samples = []
finished = threading.Event()
def sampler():
    while not finished.is_set():
        p = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8, creationflags=0x08000000)
        if p.returncode == 0:
            values = p.stdout.splitlines()[0].split(",")
            samples.append({"monotonic":time.monotonic(), "used_mib":int(values[0]), "total_mib":int(values[1])})
        finished.wait(.2)
thread = threading.Thread(target=sampler, daemon=True)
thread.start()
results=[]
try:
    for width,height in [(640,360),(960,540),(1280,720)]:
        if samples and width == 1280 and samples[-1]["total_mib"]-samples[-1]["used_mib"]<700:
            results.append({"width":width,"height":height,"skipped":"less than 700 MiB whole-GPU headroom"})
            break
        request=proto.RGBRenderRequest(scene_id=scene.scene_id,resolution_w=width,resolution_h=height,
            camera_intrinsics=camera.intrinsics,frame_start_us=int(scene.timestamps[0]),frame_end_us=int(scene.timestamps[0])+1,
            sensor_pose=proto.PosePair(start_pose=pose,end_pose=pose),image_format=proto.ImageFormat.JPEG,image_quality=95)
        times=[]
        started=time.monotonic()
        for i in range(2):
            begin=time.perf_counter()
            response=stub.render_rgb(request,timeout=30)
            times.append((time.perf_counter()-begin)*1000)
            if i == 1:(out/f"{width}x{height}.jpg").write_bytes(response.image_bytes)
        interval=[s["used_mib"] for s in samples if s["monotonic"]>=started]
        item={"width":width,"height":height,"rpc_ms_with_live_client":times,
              "observed_whole_gpu_peak_mib":max(interval) if interval else None}
        results.append(item)
        print(json.dumps(item),flush=True)
finally:
    finished.set();thread.join(timeout=10);channel.close()
    report={"method":"same source camera pose, two JPEG95 renders per resolution; live bridge remains active, so RPC includes queueing",
        "capability":capability,"results":results,"gpu_samples":samples,
        "source_unchanged":True,"not_a_benchmark_or_long_term_stability_test":True}
    (out/"result.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Private comparison:",out,flush=True)
    print("Actor capability:",json.dumps(capability),flush=True)
