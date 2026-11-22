"""Three calibrated perspective rays, one immutable NuRec scene snapshot.

No panorama stretching, copied views, synthetic side imagery or frame mixing.
The source scans can still have holes outside the captured viewing envelope.
"""
import math
import time
import numpy as np
from lab_capture import FrameBundle
from lab_settings import settings, view_yaws
from frame_validation import validate_jpeg

def camera_views(camera, cfg):
    result = {}
    # NuRec sensor matrices use OpenCV axes: right, down, forward. Positive
    # local-Y rotation turns the view right, matching CARLA's positive yaw.
    for name, yaw in view_yaws(cfg).items():
        a = math.radians(yaw); c,s = math.cos(a),math.sin(a)
        rotation = np.eye(4); rotation[:3,:3] = [[c,0,s],[0,1,0],[-s,0,c]]
        result[name] = camera @ rotation
    return result

def pinhole(proto, size, fov):
    w,h = size
    if w*9 != h*16: raise ValueError('Each lab panel must be 16:9')
    focal = w/(2*math.tan(math.radians(fov)/2))
    return proto.CameraSpec(resolution_w=w,resolution_h=h,shutter_type=proto.GLOBAL,
        opencv_pinhole_param=proto.OpenCVPinholeCameraParam(
            principal_point_x=w/2,principal_point_y=h/2,
            focal_length_x=focal,focal_length_y=focal))

class NuRecSurround:
    def __init__(self, cfg=None):
        self.config = cfg or settings(); self.frames = FrameBundle(); self.last = {}

    def render(self, stub, proto, grpc_pose, scene_id, timestamp, camera, objects, size, frame, is_current=lambda:True):
        intrinsics = pinhole(proto,size,self.config['fov'])
        poses = camera_views(camera,self.config)
        parts = {}; started = time.perf_counter()
        # Sequential calls avoid tripling peak GPU allocations. All requests
        # retain exactly the same source timestamp and frozen actor poses.
        for name in ('center','left','right'):
            pose = grpc_pose(poses[name])
            req = proto.RGBRenderRequest(scene_id=scene_id,resolution_w=size[0],resolution_h=size[1],
                camera_intrinsics=intrinsics,frame_start_us=timestamp,frame_end_us=timestamp+1,
                sensor_pose=proto.PosePair(start_pose=pose,end_pose=pose),dynamic_objects=objects,
                image_format=proto.ImageFormat.JPEG,image_quality=90)
            image = stub.render_rgb(req,timeout=300).image_bytes
            validate_jpeg(image,size,full_decode=True)
            if not is_current():return None
            parts[name] = image
        self.last = dict(frame=frame,source_timestamp_us=timestamp,panel_size=list(size),
            viewport=[5760,1080],aspect='16:3',fov=self.config['fov'],view_yaws=view_yaws(self.config),
            rpc_ms=round((time.perf_counter()-started)*1000,2),same_snapshot=True,
            wheel_animation='rigid reconstructed assets; independent wheel articulation unavailable')
        # No incomplete generation is exposed if any of the three RPCs fails.
        if not is_current():return None
        for name in ('left','center','right'): self.frames.publish(name,frame,parts[name])
        return parts['center']

    def close(self): self.frames.close()
