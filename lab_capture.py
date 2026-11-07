"""Three real camera orientations. Only a shared CARLA frame is published."""
import io,json,queue,threading,zipfile,uuid,math
from lab_settings import view_yaws

def inspection_jpeg(data,fov,target=55.):
    """Enlarge the front inspection panel without changing panorama seams."""
    from PIL import Image
    im=Image.open(io.BytesIO(data));w,h=im.size
    ratio=min(1.,math.tan(math.radians(target/2))/math.tan(math.radians(fov/2)))
    cw,ch=max(1,round(w*ratio)),max(1,round(h*ratio));left,top=(w-cw)//2,(h-ch)//2
    im=im.crop((left,top,left+cw,top+ch)).resize((w,h),Image.Resampling.LANCZOS)
    out=io.BytesIO();im.save(out,format='JPEG',quality=88);return out.getvalue()

class FrameBundle:
    def __init__(self):
        self.condition=threading.Condition();self.pending={};self.frame=-1;self.zip=None;self.closed=False;self.token=uuid.uuid4().hex
    def publish(self,view,frame,data):
        if view not in ('left','center','right'):raise ValueError('Invalid rig view')
        with self.condition:
            if self.closed or frame<=self.frame:return
            self.pending.setdefault(frame,{})[view]=data
            for stale in sorted(self.pending)[:-6]:self.pending.pop(stale,None)
            parts=self.pending.get(frame,{})
            if len(parts)==3:
                out=io.BytesIO()
                with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
                    z.writestr('frame.json',json.dumps(dict(frame=frame,token=self.token)))
                    for name in ('left','center','right'):z.writestr(name+'.jpg',parts[name])
                self.frame=frame;self.zip=out.getvalue()
                self.pending={k:v for k,v in self.pending.items() if k>frame};self.condition.notify_all()
    def after(self,frame,timeout=1.):
        with self.condition:
            self.condition.wait_for(lambda:self.frame>frame or self.closed,timeout)
            return (self.frame,self.zip) if self.frame>frame and not self.closed else (frame,None)
    def close(self):
        with self.condition:self.closed=True;self.pending.clear();self.zip=None;self.condition.notify_all()

class LabCapture:
    def __init__(self,world,ego,cfg,receive_center):
        import carla
        self.frames=FrameBundle();self.stop=threading.Event();self.cameras={};self.queues={v:queue.Queue(maxsize=1) for v in ('left','right')}
        self.config=cfg
        try:
            for name,yaw in view_yaws(cfg).items():
                bp=world.get_blueprint_library().find('sensor.camera.rgb')
                if bp.has_attribute('role_name'):bp.set_attribute('role_name','hongik_native_rig_'+name)
                # Every engine frame, so three sensors cannot start on different
                # capture phases. The viewer caps presentation at cfg['fps'].
                values=dict(image_size_x=cfg['render'][0],image_size_y=cfg['render'][1],fov=cfg['fov'],sensor_tick=0.,motion_blur_intensity=0.)
                for key,value in values.items():
                    if bp.has_attribute(key):bp.set_attribute(key,str(value))
                camera=world.spawn_actor(bp,carla.Transform(carla.Location(*cfg['eye']),carla.Rotation(pitch=cfg['pitch'],yaw=yaw)),attach_to=ego)
                self.cameras[name]=camera
                camera.listen(receive_center if name=='center' else self.receiver(name))
            for name in self.queues:threading.Thread(target=self.encode,args=(name,),daemon=True).start()
        except Exception:self.close();raise
    def receiver(self,name):
        def receive(img):
            if self.stop.is_set():return
            q=self.queues[name]
            try:q.get_nowait()
            except queue.Empty:pass
            try:q.put_nowait(img)
            except queue.Full:pass
        return receive
    def encode(self,name):
        import numpy as np
        from PIL import Image
        while not self.stop.is_set():
            try:img=self.queues[name].get(timeout=.3)
            except queue.Empty:continue
            arr=np.frombuffer(img.raw_data,dtype=np.uint8).reshape(img.height,img.width,4)
            out=io.BytesIO();Image.fromarray(arr[:,:,:3][:,:,::-1]).save(out,format='JPEG',quality=88)
            self.frames.publish(name,img.frame,out.getvalue())
    def close(self):
        self.stop.set();self.frames.close()
        for camera in self.cameras.values():
            try:camera.stop();camera.destroy()
            except RuntimeError:pass
        self.cameras.clear()
