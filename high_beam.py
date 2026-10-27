"""Acknowledged two-flash signal and local headlight compositing.

The NuRec checkpoint has baked illumination. This is an explicitly approximate
beam/box/ground lighting pass, paired with CARLA's real vehicle light state.
No extra neural model, checkpoint edits, or claim of physical light transport.
"""
import io
import numpy as np
from PIL import Image


class HighBeamSignal:
    # Each stage must actually reach the driving stream before it can end.
    STAGES=((True,1.0),(False,.65),(True,1.0),(False,.35))

    def __init__(self):
        self.count=0;self.stage=-1;self.elapsed=0.;self.ack=False;self.finished=False

    def begin(self):
        self.count+=1;self.stage=0;self.elapsed=0.;self.ack=False;self.finished=False

    def advance(self,dt,driving):
        if not driving or self.stage<0 or self.finished:return
        self.elapsed+=min(max(dt,0.),.2)
        if self.ack and self.elapsed>=self.STAGES[self.stage][1]:
            self.stage+=1;self.elapsed=0.;self.ack=False
            if self.stage==len(self.STAGES):self.finished=True

    def acknowledge(self,sequence,stage):
        if sequence==self.count and stage==self.stage and 0<=stage<len(self.STAGES) and not self.finished:self.ack=True

    def public(self):
        on=0<=self.stage<len(self.STAGES) and self.STAGES[self.stage][0]
        return dict(sequence=self.count,stage=self.stage,on=bool(on),intensity=1. if on else 0.,
                    completed=self.finished,frame_acknowledged=self.ack)


class HighBeamEffect:
    WIDTH,HEIGHT=240,135

    def __init__(self):
        # Precompute exposure curves once. Full-HD frames then need only an
        # 8-bit lookup rather than several large floating-point RGB temporaries.
        amount=np.arange(256,dtype=np.float32)[:,None,None]/255.
        value=np.arange(256,dtype=np.float32)[None,:,None]/255.
        illumination=amount*np.array([1.,.975,.91],dtype=np.float32)
        linear=value**2.2;gain=np.exp2(illumination*2.3)
        result=(linear*gain/(1.+linear*(gain-1.)))**(1./2.2)
        self.lut=np.uint8(np.rint(np.clip(result,0,1)*255))

    def configure(self,intrinsics):
        if intrinsics.WhichOneof('camera_param')!='ftheta_param':raise ValueError('Expected calibrated f-theta camera')
        p=intrinsics.ftheta_param;y,x=np.mgrid[:self.HEIGHT,:self.WIDTH]
        dx=(x+.5)*intrinsics.resolution_w/self.WIDTH-p.principal_point_x
        dy=(y+.5)*intrinsics.resolution_h/self.HEIGHT-p.principal_point_y
        rho=np.hypot(dx,dy);theta=np.polynomial.polynomial.polyval(rho,list(p.pixeldist_to_angle_poly))
        self.rays=np.stack((np.sin(theta)*dx/np.maximum(rho,1e-8),np.sin(theta)*dy/np.maximum(rho,1e-8),np.cos(theta)),axis=-1).reshape(-1,3)

    @staticmethod
    def box_range(origin,rays,pose,size):
        local_origin=(origin-pose[:3,3])@pose[:3,:3]
        local_rays=np.einsum('ni,ij->nj',rays,pose[:3,:3])
        safe=np.where(np.abs(local_rays)<1e-8,1e-8,local_rays)
        lo=(-np.asarray(size)/2.-local_origin)/safe;hi=(np.asarray(size)/2.-local_origin)/safe
        near=np.minimum(lo,hi).max(axis=1);far=np.maximum(lo,hi).min(axis=1)
        return np.where((far>=near)&(near>.1),near,np.inf)

    def apply(self,jpeg,camera,ego,ground,normal,actors,signal):
        record=dict(signal,method='approximate calibrated-ray ground/vehicle lighting; not neural relighting')
        if not signal['on']:return jpeg,dict(record,mean_lift=0.,lit_fraction=0.)
        rays=np.einsum('ni,ji->nj',self.rays,camera[:3,:3]);origin=camera[:3,3]
        denominator=np.einsum('ni,i->n',rays,normal)
        depth=np.divide(np.dot(ground-origin,normal),denominator,out=np.full(len(rays),np.inf),where=np.abs(denominator)>1e-6)
        depth=np.where(depth>.2,depth,np.inf)
        for pose,size in actors:
            if np.linalg.norm(pose[:3,3]-origin)<110:
                depth=np.minimum(depth,self.box_range(origin,rays,pose,size))
        valid=np.isfinite(depth)&(depth<120)
        positions=np.einsum('ni,ij->nj',origin+rays*np.where(valid,depth,0)[:,None]-ego[:3,3],ego[:3,:3])
        light=np.zeros(len(rays),dtype=np.float32)
        for lateral in (-.62,.62):
            delta=positions-np.array([1.8,lateral,.55]);forward=delta[:,0]
            horizontal=np.arctan2(delta[:,1],forward);vertical=np.arctan2(delta[:,2],forward)
            cone=np.exp(-.5*(horizontal/.24)**4-.5*(vertical/.18)**2)
            falloff=1./(1.+(np.linalg.norm(delta,axis=1)/55.)**2)
            light+=np.where(valid&(forward>.5),cone*falloff,0.)*.42
        mask=Image.fromarray(np.uint8(np.clip(light.reshape(self.HEIGHT,self.WIDTH),0,.78)*255))
        with Image.open(io.BytesIO(jpeg)) as picture:
            rgb=np.asarray(picture.convert('RGB'))
            amount=np.asarray(mask.resize(picture.size,Image.Resampling.BILINEAR))
        # Smooth diffuse lift on the beam-hit road and vehicle surfaces, no white
        # triangle pasted over the scene; sky/upward rays receive no light.
        result=self.lut[amount[...,None],rgb,np.arange(3)]
        output=io.BytesIO();Image.fromarray(result).save(output,format='JPEG',quality=95)
        record.update(mean_lift=round(float(result.mean()-rgb.mean())/255.,5),lit_fraction=round(float((amount>25).mean()),4))
        return output.getvalue(),record
