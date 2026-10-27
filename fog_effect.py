"""Range-aware atmospheric compositing with same-frame native distance when available.

Native distance or approximate point-splat fallback; atmospheric compositing is not real fog physics.
No auxiliary neural model, no change to the source checkpoint, no camera overlay UI.
"""
import io
import math
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import minimum_filter,uniform_filter
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parent.parent


def transmission(distance,beta):
    return np.exp(-np.asarray(distance,dtype=np.float32)*np.maximum(0.,np.asarray(beta,dtype=np.float32)))


# A nonlinear fog-strength table resolves near-clear dark pixels finely while
# keeping the complete RGB/airlight blend in a small CPU-cache-sized lookup.
_GAMMA_DECODE=(np.arange(256,dtype=np.float32)/255.)**2.2
_AIR_LINEAR=np.array([.79,.82,.84],dtype=np.float32)**2.2
_FOG_AMOUNT=(np.arange(2048,dtype=np.float32)/2047.)**2
_FOG_LUT=np.uint8(np.rint((
    _GAMMA_DECODE[None,:,None]*(1.-_FOG_AMOUNT[:,None,None])
    +_AIR_LINEAR*_FOG_AMOUNT[:,None,None])**(1./2.2)*255.))


def composite_fog_rgb(rgb,transmittance):
    amount=np.uint16(np.rint(np.sqrt(np.clip(1.-transmittance,0.,1.))*2047.))
    return _FOG_LUT[amount,rgb,np.arange(3)]


def fog_query_radius(beta):
    # The spatial density modulation is bounded by +/-0.09. At this
    # conservative radius, retained background transmittance is <=1/2048.
    # Geometry beyond it contributes less than an 8-bit colour step.
    return min(240.,math.log(2048.)/(max(float(beta),1e-8)*.9))


class FogEffect:
    def __init__(self):
        folder=ROOT/'cache/fog'
        self.meta=json.loads((folder/'highway-range-geometry.json').read_text())
        self.camera=self.meta['camera']
        self.width,self.height=240,135
        y,x=np.mgrid[:self.height,:self.width]
        self.x=x/self.width;self.y=y/self.height
        self.update_rays()

    def update_rays(self):
        native_w,native_h=self.camera['resolution'];cx,cy=self.camera['principal_point']
        dx=(self.x+.5/self.width)*native_w-cx
        dy=(self.y+.5/self.height)*native_h-cy
        rho=np.hypot(dx,dy)
        angle=np.polynomial.polynomial.polyval(rho,self.camera['pixeldist_to_angle_poly'])
        self.rays=np.stack((np.sin(angle)*dx/np.maximum(rho,1e-8),np.sin(angle)*dy/np.maximum(rho,1e-8),np.cos(angle)),axis=-1)

    def configure(self,camera):
        # Use the same calibrated lens as the RGB request, not an assumed pinhole.
        if camera.WhichOneof('camera_param')!='ftheta_param':
            raise ValueError('Expected the source front-wide f-theta calibration')
        p=camera.ftheta_param
        self.camera=dict(self.camera,principal_point=[p.principal_point_x,p.principal_point_y],
            angle_to_pixeldist_poly=list(p.angle_to_pixeldist_poly),
            pixeldist_to_angle_poly=list(p.pixeldist_to_angle_poly))
        self.update_rays()

    def project(self,points,cam):
        local=(points-cam[:3,3])@cam[:3,:3]
        r=np.linalg.norm(local[:,:2],axis=1)
        theta=np.arctan2(r,local[:,2])
        rho=np.polynomial.polynomial.polyval(theta,self.camera['angle_to_pixeldist_poly'])
        cx,cy=self.camera['principal_point'];native_w,native_h=self.camera['resolution']
        px=(local[:,0]/np.maximum(r,1e-8)*rho+cx)*self.width/native_w
        py=(local[:,1]/np.maximum(r,1e-8)*rho+cy)*self.height/native_h
        ranges=np.linalg.norm(local,axis=1)
        keep=(local[:,2]>.1)&(theta<self.camera['max_angle'])&(px>=0)&(px<self.width)&(py>=0)&(py<self.height)&(ranges<350)
        return px[keep].astype(np.int32),py[keep].astype(np.int32),ranges[keep]

    def ranges(self,source_camera,lead_source_pose,max_range=240.):
        if not hasattr(self,'points'):
            with np.load(ROOT/'cache/fog/highway-range-geometry.npz',allow_pickle=False) as data:
                self.points=data['static'];self.lead=data['lead'];self.world_to_nre=data['world_to_nre']
            self.tree=cKDTree(self.points[:,:2])
            self.road=self.points[self.meta['counts']['background']:]
            self.road_tree=cKDTree(self.road[:,:2])
        cam=self.world_to_nre@source_camera
        indices=self.tree.query_ball_point(cam[:2,3],max_range,return_sorted=False)
        selected=self.points[indices]
        if lead_source_pose is not None:
            lead_pose=self.world_to_nre@lead_source_pose
            moving=self.lead@lead_pose[:3,:3].T+lead_pose[:3,3]
            selected=np.concatenate((selected,moving))
        x,y,r=self.project(selected,cam)
        depth=np.full((self.height,self.width),np.inf,dtype=np.float32)
        np.minimum.at(depth,(y,x),r)
        # Fill tiny sampling gaps only, without dilating a foreground silhouette.
        holes=~np.isfinite(depth)
        neighbours=minimum_filter(depth,size=3)
        depth[holes]=neighbours[holes]
        # The measured road Gaussian layer supplies a local ground plane. It
        # prevents missing ground samples from turning into floating white holes.
        road_indices=self.road_tree.query_ball_point(cam[:2,3],28.)
        if len(road_indices)>30:
            road=self.road[road_indices]-cam[:3,3]
            plane=np.linalg.lstsq(np.column_stack((road[:,:2],np.ones(len(road)))),road[:,2],rcond=None)[0]
            rays=self.rays@cam[:3,:3].T
            denominator=rays[:,:,2]-plane[0]*rays[:,:,0]-plane[1]*rays[:,:,1]
            ground=np.divide(plane[2],denominator,out=np.full(denominator.shape,np.inf),where=denominator<-.0001)
            ground[(ground<0)|(ground>180.)]=np.inf
            depth=np.minimum(depth,ground).astype(np.float32)
        depth[~np.isfinite(depth)]=500.
        return depth,len(selected)

    def apply(self,jpeg,source_camera,lead_source_pose,scenario,native_ranges=None):
        fog=scenario['fog'];beta=float(fog['beta'])
        if beta<=0:return jpeg,dict(applied=False,stage='clear',beta=0.,method='unchanged RGB')
        radius=fog_query_radius(beta)
        native=(native_ranges is not None and native_ranges.shape==(self.height,self.width)
            and np.isfinite(native_ranges).all() and np.all((native_ranges>=.09)&(native_ranges<=500.)))
        if native:
            ranges=native_ranges;count=0
        else:
            ranges,count=self.ranges(source_camera,lead_source_pose,max_range=radius)
        t=float(scenario['elapsed_s'])
        # Smooth moving density variation, continuous in driving time (pause freezes it).
        eddies=(.055*np.sin(self.x*13.+self.y*7.+t*.17)+
                 .035*np.sin(self.x*7.-self.y*9.-t*.11))
        field=transmission(ranges,beta*(1.+eddies))
        with Image.open(io.BytesIO(jpeg)) as original:
            size=original.size;rgb=np.asarray(original.convert('RGB'))
        # Edge-guided upsampling ties fog boundaries to the actual RGB image.
        # Unlike broad minimum filters, this avoids a clear rectangular halo.
        guide=rgb@np.array([.299/255.,.587/255.,.114/255.],dtype=np.float32)
        small=np.asarray(Image.fromarray(guide).resize((self.width,self.height),Image.Resampling.BILINEAR))
        mean_i=uniform_filter(small,7);mean_p=uniform_filter(field,7)
        variance=uniform_filter(small*small,7)-mean_i*mean_i
        covariance=uniform_filter(small*field,7)-mean_i*mean_p
        a=covariance/(variance+.001)
        b=mean_p-a*mean_i
        a=np.asarray(Image.fromarray(uniform_filter(a,7).astype(np.float32)).resize(size,Image.Resampling.BILINEAR))
        b=np.asarray(Image.fromarray(uniform_filter(b,7).astype(np.float32)).resize(size,Image.Resampling.BILINEAR))
        enlarged=np.clip(a*guide+b,0.,1.)[:,:,None]
        result=Image.fromarray(composite_fog_rgb(rgb,enlarged))
        stream=io.BytesIO();result.save(stream,format='JPEG',quality=94)
        return stream.getvalue(),dict(applied=True,stage=fog['stage'],beta=beta,
            method=('same-frame native renderer range' if native else 'reconstructed Gaussian centre range')+' + Beer-Lambert compositing',
            range_source='native_same_frame' if native else 'point_geometry_fallback',
            approximate=True,points=count,static_query_radius_m=round(radius,2),range_grid=[self.width,self.height],
            transmission_mean=float(field.mean()),transmission_near=float(field[ranges<8].mean()) if np.any(ranges<8) else None)


