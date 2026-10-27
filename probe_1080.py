"""Private still comparison from one unchanged pretrained scene, not an upscale."""
import io
import json
import time
from pathlib import Path
import grpc
from PIL import Image
from scene_bridge import Scene, grpc_pose, proto, SensorsimServiceStub
from scenario2 import Route, Scenario2

root = Path(__file__).resolve().parent
out = root / 'validation' / ('native-1080-' + time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True, exist_ok=False)
scene = Scene()
channel = grpc.insecure_channel('127.0.0.1:46435', options=[('grpc.max_receive_message_length', 32*1024*1024)])
stub = SensorsimServiceStub(channel)
camera = next(c for c in stub.get_available_cameras(proto.AvailableCamerasRequest(scene_id=scene.scene_id), timeout=30).available_cameras if c.logical_id == scene.camera_id)
catalog = stub.get_dynamic_objects(proto.AvailableDynamicObjectsRequest(scene_id=scene.scene_id), timeout=30)
lead = next(o for o in catalog.dynamic_objects if o.id == Scenario2.TRACK_ID)
sensor = grpc_pose(scene.poses[0] @ scene.camera_mount)
car = grpc_pose(scene.inverse_alignment @ Route(scene.route).sample(20., 0., 0., lead.object_size.size_z/2))
objects = [proto.DynamicObject(track_id=Scenario2.TRACK_ID, pose_pair=proto.PosePair(start_pose=car, end_pose=car))]
results = []
try:
    for w, h in [(960, 540), (1920, 1080)]:
        request = proto.RGBRenderRequest(scene_id=scene.scene_id, resolution_w=w, resolution_h=h,
            camera_intrinsics=camera.intrinsics, frame_start_us=scene.start_us, frame_end_us=scene.start_us+1,
            sensor_pose=proto.PosePair(start_pose=sensor, end_pose=sensor), dynamic_objects=objects,
            image_format=proto.ImageFormat.JPEG, image_quality=95)
        started = time.perf_counter()
        image = stub.render_rgb(request, timeout=180).image_bytes
        elapsed = time.perf_counter() - started
        with Image.open(io.BytesIO(image)) as im:
            im.load()
            assert im.size == (w, h), im.size
        (out / f'{w}x{h}.jpg').write_bytes(image)
        results.append(dict(width=w, height=h, rpc_seconds=elapsed, bytes=len(image)))
        print(json.dumps(results[-1]), flush=True)
finally:
    (out/'result.json').write_text(json.dumps(dict(results=results, source_unchanged=True,
        same_camera_time_actor=True, model_retrained=False, native_render_not_upscale=True,
        private_internal_trial=True, single_still_not_realtime_benchmark=True), indent=2))
    channel.close()
    print(out, flush=True)
