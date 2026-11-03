"""Frame-matched native walker compositing for the pinned CARLA 0.9.16.

This is a local hybrid implementation, not CARLA UE5's official hybrid backend.
RGB, instance IDs and metric depth must share a CARLA frame. They are reprojected
through the actual calibrated f-theta rays, with same-request NuRec range for
occlusion. Baked night lighting is approximated; no neural relighting claim.
"""
import io
import math
import threading
import time
from collections import OrderedDict
import cv2
import numpy as np
from PIL import Image
cv2.setNumThreads(2)

MIRROR=np.diag([1.,-1.,1.,1.])
# Optical coordinates (right, down, forward) -> CARLA (forward, right, up).
OPTICAL_TO_CARLA=np.array([[0,0,1,0],[1,0,0,0],[0,-1,0,0],[0,0,0,1]],float)


def optical_pose(alignment,camera_transform):
    return np.linalg.inv(alignment)@MIRROR@camera_transform@OPTICAL_TO_CARLA


def left_transform(matrix):
    import carla
    return carla.Transform(carla.Location(*matrix[:3,3].tolist()),carla.Rotation(
        yaw=math.degrees(math.atan2(matrix[1,0],matrix[0,0])),
        pitch=math.degrees(math.atan2(matrix[2,0],math.hypot(matrix[0,0],matrix[1,0]))),
        roll=math.degrees(math.atan2(-matrix[2,1],matrix[2,2]))))


def lens_maps(intrinsics,size,native_size,fov):
    width,height=size;nw,nh=native_size;p=intrinsics.ftheta_param
    y,x=np.mgrid[:height,:width]
    dx=(x+.5)*intrinsics.resolution_w/width-p.principal_point_x
    dy=(y+.5)*intrinsics.resolution_h/height-p.principal_point_y
    rho=np.hypot(dx,dy);theta=np.polynomial.polynomial.polyval(rho,list(p.pixeldist_to_angle_poly))
    rays=np.stack((np.sin(theta)*dx/np.maximum(rho,1e-8),np.sin(theta)*dy/np.maximum(rho,1e-8),np.cos(theta)),axis=-1).astype(np.float32)
    focal=nw/(2*math.tan(math.radians(fov)/2))
    u=(focal*rays[...,0]/np.maximum(rays[...,2],1e-6)+nw/2-.5).astype(np.float32)
    v=(focal*rays[...,1]/np.maximum(rays[...,2],1e-6)+nh/2-.5).astype(np.float32)
    valid=(rays[...,2]>0)&(u>=1)&(u<nw-2)&(v>=1)&(v<nh-2)
    return u,v,rays,valid


def same_background(old_pose,old_stamp,pose,stamp):
    # Stationary reuse only: tight bounds avoid hiding camera/traffic changes.
    return bool(old_pose is not None and abs(stamp-old_stamp)<=2000
        and np.linalg.norm(old_pose[:3,3]-pose[:3,3])<.002
        and np.max(np.abs(old_pose[:3,:3]-pose[:3,:3]))<.0001)


class FramePairs:
    def __init__(self):self.lock=threading.Condition();self.pending=OrderedDict();self.latest=None
    def offer(self,kind,image):
        with self.lock:
            row=self.pending.setdefault(image.frame,{})
            row[kind]=image
            if len(row)==3 and (self.latest is None or image.frame>self.latest[0]):
                self.latest=(image.frame,row,time.monotonic());self.lock.notify_all()
            while len(self.pending)>8:self.pending.popitem(last=False)
    def get(self,timeout=6.):
        deadline=time.monotonic()+timeout
        with self.lock:
            while self.latest is None or time.monotonic()-self.latest[2]>.8:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise RuntimeError('Hybrid cameras did not deliver a fresh, frame-matched RGB/ID/depth set')
                self.lock.wait(min(.2,remaining))
            return self.latest


class HybridPedestrian:
    SIZE=(960,540);FOV=100.
    def __init__(self,bridge):
        import carla
        from pedestrian_yield import YieldActor
        self.bridge=bridge;self.pairs=FramePairs();self.maps={}
        self.walker=YieldActor(bridge.world,bridge.scenario.crossing_route)
        bridge.scenario.pedestrian=self.walker;bridge.actors.append(self.walker.actor)
        world=bridge.world
        weather=world.get_weather();weather.sun_altitude_angle=-10.;weather.cloudiness=15.
        weather.precipitation=0.;weather.fog_density=0.;world.set_weather(weather)
        bridge.ego.set_light_state(carla.VehicleLightState(carla.VehicleLightState.Position|carla.VehicleLightState.LowBeam))
        mount=MIRROR@bridge.scene.camera_mount@np.linalg.inv(OPTICAL_TO_CARLA)
        local=left_transform(mount)
        for kind,name in [('rgb','rgb'),('ids','instance_segmentation'),('depth','depth')]:
            bp=world.get_blueprint_library().find('sensor.camera.'+name)
            if bp.has_attribute('role_name'):bp.set_attribute('role_name','nurec_hybrid_'+kind)
            for key,val in dict(image_size_x=self.SIZE[0],image_size_y=self.SIZE[1],fov=self.FOV,sensor_tick=.05).items():bp.set_attribute(key,str(val))
            if kind=='rgb':
                for key,val in dict(motion_blur_intensity=0.,bloom_intensity=.15,exposure_compensation=.3,
                    exposure_mode='manual',shutter_speed=60.,iso=800.,fstop=1.4).items():
                    if bp.has_attribute(key):bp.set_attribute(key,str(val))
            sensor=world.spawn_actor(bp,local,attach_to=bridge.ego,attachment_type=carla.AttachmentType.Rigid)
            bridge.actors.append(sensor);sensor.listen(lambda image,k=kind:self.pairs.offer(k,image))
        self.cached_pose=None;self.cached_stamp=None;self.cached_jpeg=None;self.cached_range=None;self.cached_size=None
        self.beam=None
        self.paint_source=None;self.painted_background=None;self.background_range=None
        self.last_record={}

    def capture(self):
        frame,row,received=self.pairs.get()
        native=np.array(row['rgb'].transform.get_matrix())
        camera=optical_pose(self.bridge.scene.alignment,native)
        # Recover ego at precisely the sensor exposure, never a newer snapshot.
        ego_left=native@np.linalg.inv(MIRROR@self.bridge.scene.camera_mount@np.linalg.inv(OPTICAL_TO_CARLA))
        return frame,row,camera,left_transform(ego_left),time.monotonic()-received

    def compose(self,jpeg,row,camera,size,ranges,scenario):
        if size not in self.maps:self.maps[size]=lens_maps(self.bridge.intrinsics,size,self.SIZE,self.FOV)
        u,v,rays,valid=self.maps[size];nw,nh=self.SIZE
        def raw(kind):return np.frombuffer(row[kind].raw_data,dtype=np.uint8).reshape(nh,nw,4)
        ids=raw('ids')
        # Instance ID in G/B, semantic tag in R. Target only our walker, never
        # a reconstructed traffic proxy or another native actor.
        target=self.walker.actor.id&65535
        mask=(ids[...,1]==target%256)&(ids[...,0]==target//256)&np.isin(ids[...,2],list(self.walker.actor.semantic_tags))
        if ranges is None:raise RuntimeError('Hybrid occlusion requires range from this exact NuRec request')
        if self.paint_source is not jpeg or self.painted_background.shape[:2]!=(size[1],size[0]):
            self.background_range=cv2.resize(ranges,size,interpolation=cv2.INTER_NEAREST)
            self.painted_background=self.crossing(np.array(Image.open(io.BytesIO(jpeg)).convert('RGB')),camera,self.background_range,rays)
            self.paint_source=jpeg
        background_range=self.background_range
        image=self.painted_background.copy();pixels=0
        bx,by,bw,bh=cv2.boundingRect(mask.astype(np.uint8))
        if bw and bh:
            bx,by=max(0,bx-2),max(0,by-2);bw,bh=min(nw-bx,bw+4),min(nh-by,bh+4)
            # Lens maps are shared, but RGB/depth/alpha work is confined to the
            # pedestrian rectangle. No three full-screen floating-point layers.
            covered=valid&(u>=bx)&(u<bx+bw-1)&(v>=by)&(v<by+bh-1)
            ox,oy,ow,oh=cv2.boundingRect(covered.astype(np.uint8))
            if ow and oh:
                region=np.s_[oy:oy+oh,ox:ox+ow];native_region=np.s_[by:by+bh,bx:bx+bw]
                ru,rv=u[region]-bx,v[region]-by
                rgb=cv2.cvtColor(raw('rgb')[native_region],cv2.COLOR_BGRA2RGB)
                depth=raw('depth')[native_region]
                metric=(depth[...,2].astype(np.float32)+depth[...,1].astype(np.float32)*256+depth[...,0].astype(np.float32)*65536)*(1000./16777215.)
                alpha=cv2.remap(mask[native_region].astype(np.float32),ru,rv,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
                foreground=cv2.remap(rgb,ru,rv,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
                # Native depth is view-axis distance; the neural hint is range.
                native_range=cv2.remap(metric,ru,rv,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)/np.maximum(rays[region][...,2],1e-6)
                alpha*=valid[region]&(native_range<=background_range[region]+.35)
                color=foreground.astype(np.float32)*np.array([.91,.95,1.],np.float32)
                image[region]=np.uint8(np.clip(image[region]*(1-alpha[...,None])+color*alpha[...,None],0,255))
                pixels=int((alpha>.5).sum())
        # Keep a narrow antialiased edge. Source baked light and native dynamic
        # light remain separate; modest grading reduces the obvious day-lit cutout.
        out=io.BytesIO();Image.fromarray(image).save(out,format='JPEG',quality=95)
        result=out.getvalue()
        if self.beam is None:
            from high_beam import HighBeamEffect
            self.beam=HighBeamEffect();self.beam.configure(self.bridge.intrinsics)
        signal=scenario['high_beam']
        if signal['on']:
            b=self.bridge;tr=b.ego.get_transform()
            ego=b.scene.inverse_alignment@MIRROR@np.array(tr.get_matrix())@MIRROR
            centre,_=b.scenario.crossing_route.sample(b.scenario.ego_s)
            ground=b.scene.inverse_alignment@np.array([centre[0],-centre[1],centre[2],1.])
            result,_=self.beam.apply(result,camera,ego,ground[:3],b.scene.inverse_alignment[:3,2],[],signal)
        self.last_record=dict(native_frame=row['rgb'].frame,mask_pixels=pixels,
            native_mask_pixels=int(mask.sum()),walker_id=self.walker.actor.id,
            method='matched native RGB/instance/depth, calibrated f-theta warp, same-request neural range',
            crossing='added experimental road marking; not recorded source topology',
            approximate_lighting=True)
        return result

    def crossing(self,image,camera,ranges,rays):
        """A restrained added zebra on the measured ground, range-occluded."""
        bridge=self.bridge;r=bridge.scenario.crossing_route
        origin_source=camera[:3,3]
        # Transform calibrated world rays into CARLA left-handed coordinates.
        cam_left=MIRROR@bridge.scene.alignment@camera
        world_rays=rays@cam_left[:3,:3].T;origin=cam_left[:3,3]
        centre,yaw=r.sample(r.cross_s);normal=np.array([0.,0.,1.])
        denom=world_rays[...,2]
        distance=np.divide(centre[2]+.015-origin[2],denom,out=np.full(denom.shape,np.inf,dtype=np.float32),where=np.abs(denom)>1e-6)
        hits=origin+world_rays*np.where(np.isfinite(distance),distance,0)[...,None]
        forward=np.array([math.cos(yaw),math.sin(yaw),0]);right=np.array([-forward[1],forward[0],0])
        s=(hits-centre)@forward;off=(hits-centre)@right
        painted=(distance>.2)&(distance<55)&(distance<ranges+.5)&(abs(s)<1.3)&(off>-4.2)&(off<5.2)&(np.mod(off+4.2,.95)<.48)
        # Reflectance change preserves the original road texture, unlike a white plate.
        image=image.copy();image[painted]=np.uint8(np.clip(image[painted].astype(np.float32)*.5+94,0,255))
        return image
