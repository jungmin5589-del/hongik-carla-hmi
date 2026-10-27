"""Same-request low-resolution native range; no second render or cached-frame reuse."""

def encode_range_hint(distance,opacity,timestamp):
    import struct,zlib,torch
    if distance is None:return None
    height,width=135,240
    value=torch.nn.functional.interpolate(distance.detach().float()[None,None],size=(height,width),mode='nearest')[0,0]
    valid=torch.isfinite(value)&(value>.1)
    if opacity is not None:
        alpha=torch.nn.functional.interpolate(opacity.detach().float()[None,None],size=(height,width),mode='nearest')[0,0]
        valid=valid&(alpha>=.5)
        value=value/alpha.clamp_min(1e-6)
    value=torch.where(valid,value.clamp(.1,500.),torch.full_like(value,500.))
    raw=value.to(torch.float16).cpu().numpy().astype('<f2',copy=False).tobytes()
    return struct.pack('<4sHHQ',b'NRD1',width,height,int(timestamp))+zlib.compress(raw,1)



def compose_native_fog(color,distance,opacity,beta,seconds,rays=None):
    """Atmospheric composite on same-frame native surface ranges, before JPEG."""
    import torch
    if distance is None:return None
    height,width=distance.shape
    y=torch.arange(height,device=color.device,dtype=torch.float32)[:,None]/height
    x=torch.arange(width,device=color.device,dtype=torch.float32)[None,:]/width
    eddies=.025*torch.sin(x*13.+y*7.+seconds*.07)+.015*torch.sin(x*7.-y*9.-seconds*.05)
    valid=torch.isfinite(distance)&(distance>.1)
    if opacity is not None:
        valid=valid&(opacity>=.5)
        distance=distance/opacity.clamp_min(1e-6)
    ranges=torch.where(valid,distance.clamp(.1,500.),torch.full_like(distance,500.))
    if rays is not None:
        # Complete only unreliable near-road pixels from a plane fitted to
        # reliable same-frame bottom-road hits; no point-cloud search.
        ys=slice(height*7//8,height,max(1,height//32))
        xs=slice(width//4,width*3//4,max(1,width//32))
        direction=rays[...,3:6].float()
        origins=rays[...,:3].float()-rays[0,0,:3].float()
        # Work in a basis derived from this calibrated camera. Reconstructed
        # model coordinates need not use global Z as their vertical axis.
        right=direction[height//2,width*3//4]-direction[height//2,width//4]
        right=right/torch.linalg.vector_norm(right).clamp_min(1e-8)
        forward=direction[height//2,width//2]
        down=torch.linalg.cross(forward,right)
        down=down/torch.linalg.vector_norm(down).clamp_min(1e-8)
        forward=torch.linalg.cross(right,down)
        basis=torch.stack((right,down,forward),dim=1)
        direction=direction@basis;origins=origins@basis
        hits=origins[ys,xs]+direction[ys,xs]*ranges[ys,xs,None]
        confidence=((opacity-.5)/.45).clamp(0.,1.) if opacity is not None else torch.ones_like(distance)
        confidence=confidence*confidence*(3.-2.*confidence)
        weight=((valid[ys,xs]&(ranges[ys,xs]>.5)&(ranges[ys,xs]<30.)).float()*confidence[ys,xs]).flatten()
        hits=hits.reshape(-1,3)
        # Center the fit so regularization cannot bias the camera/ground
        # height and amplify a tiny near-road error into a far-road band.
        centre=(hits*weight[:,None]).sum(0)/weight.sum().clamp_min(1e-6)
        xz=hits[:,[0,2]]-centre[[0,2]];y_vertical=hits[:,1]-centre[1]
        normal=xz.T@(xz*weight[:,None])+torch.eye(2,device=color.device)*1e-4
        slope=torch.linalg.solve(normal,xz.T@(y_vertical*weight))
        coef=torch.cat((slope,(centre[1]-slope@centre[[0,2]])[None]))
        denominator=direction[...,1]-coef[0]*direction[...,0]-coef[1]*direction[...,2]
        numerator=coef[0]*origins[...,0]+coef[1]*origins[...,2]+coef[2]-origins[...,1]
        ground=numerator/torch.where(denominator.abs()>1e-5,denominator,torch.full_like(denominator,1e-5))
        # A 30m cutoff made low-confidence roadside geometry jump abruptly to
        # the 500m sky sentinel: white bands instead of continuous ground fog.
        # Extend the same measured local plane only to downward ground hits.
        plausible=(weight.sum()>=8)&(coef[2]>.25)&(coef[2]<4.)&(torch.linalg.vector_norm(coef[:2])<1.2)
        fill=plausible&torch.isfinite(ground)&(denominator>.0001)&(ground>.5)&(ground<500.)
        # A reconstructed grass/shoulder may be opaque but incorrectly placed
        # far behind the local road. Alpha alone is not geometric confidence.
        # Keep nearer vehicles/vegetation; cap impossible far ground hits.
        completed=torch.minimum(ranges,ground)
        ranges=torch.where(fill,completed,ranges)
    transmittance=torch.exp(-ranges*beta*(1.+eddies))[...,None]
    air=torch.tensor([.79,.82,.84],device=color.device,dtype=torch.float32).pow(2.2)
    return (color.clamp(0.,1.).pow(2.2)*transmittance+air*(1.-transmittance)).clamp(0.,1.).pow(1./2.2)

def decode_range_hint(payload,timestamp):
    import struct,zlib,numpy as np
    if not isinstance(payload,bytes) or not 16<len(payload)<128*1024:return None
    magic,width,height,stamp=struct.unpack('<4sHHQ',payload[:16])
    if magic!=b'NRD1' or (width,height)!=(240,135) or stamp!=int(timestamp):return None
    expected=width*height*2
    try:
        decoder=zlib.decompressobj();raw=decoder.decompress(payload[16:],expected+1)
    except zlib.error:return None
    if len(raw)!=expected or not decoder.eof or decoder.unused_data:return None
    value=np.frombuffer(raw,dtype='<f2').astype(np.float32).reshape(height,width)
    if not np.isfinite(value).all() or np.any((value<.09)|(value>500.)):return None
    return value

