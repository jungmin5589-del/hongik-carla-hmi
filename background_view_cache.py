"""Conservative inference-only static background selection, before collection.

Cache raw parameters, not evaluated appearance or vehicle poses. The road and
actors never enter this helper. Sources stay read-only, with one cached view.
"""
import math
import weakref


def background_view_parameters(node,parameters,rendering_data):
    import torch, os
    if os.path.exists('/tmp/nurec-static-view-bypass'):
        node._nurec_background_view_cache=None
        return parameters
    if node.training or torch.is_grad_enabled():return parameters
    if torch.distributed.is_initialized() and torch.distributed.get_world_size()!=1:return parameters
    if getattr(node,'cuboid_tracks',None) is not None:return parameters
    if type(node.scale_activation).__name__!='ExpActivation':return parameters
    sensor=rendering_data.sensor_model_parameters[0]
    half_angle=getattr(sensor,'max_angle',None)
    if half_angle is None or not 0.<float(half_angle)<math.pi-.1:return parameters
    count=len(parameters['positions'])
    if count<128 or any(v.ndim==0 or len(v)!=count for v in parameters.values()):return parameters
    try:versions=tuple((k,v._version) for k,v in parameters.items())
    except RuntimeError:return parameters
    eyes=rendering_data.poses_tquat_startend[0].detach().cpu().double()
    if not bool(torch.isfinite(eyes).all()):return parameters
    center=eyes[0,:3];quats=eyes[:,3:];quats=quats/torch.linalg.vector_norm(quats,dim=1,keepdim=True).clamp_min(1e-12)
    q=quats[0];entry=getattr(node,'_nurec_background_view_cache',None)
    def inside(previous_center,previous_q):
        distances=torch.linalg.vector_norm(eyes[:,:3]-previous_center,dim=1)
        dots=(quats@previous_q).abs().clamp(0.,1.)
        return bool((distances<=2.).all() and (dots>=math.cos(.02/2)).all())
    if entry is not None and entry['versions']==versions and entry['half_angle']==float(half_angle) and all(
            entry['sources'].get(k,lambda:None)() is v for k,v in parameters.items()) and inside(entry['center'],entry['q']):
        return entry['selected']
    node._nurec_background_view_cache=None
    entry=None
    if not inside(center,q):return parameters
    x,y,z,w=q.tolist()
    rotation=torch.tensor([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]],device=parameters['positions'].device,dtype=parameters['positions'].dtype)
    center_gpu=center.to(parameters['positions']);parts=[]
    # Bound temporary work; no whole-scene camera transform every frame.
    for start in range(0,count,500000):
        end=min(count,start+500000)
        local=(parameters['positions'][start:end]-center_gpu)@rotation
        distance=torch.linalg.vector_norm(local,dim=1).clamp_min(1e-8)
        radius=parameters['scales'][start:end].exp().amax(1)*8.+2.
        angle=torch.atan2(torch.linalg.vector_norm(local[:,:2],dim=1),local[:,2])
        keep=(radius>=distance)|(angle<=float(half_angle)+torch.asin((radius/distance).clamp(0.,1.))+.04)
        parts.append(torch.nonzero(keep,as_tuple=False).flatten()+start)
    indices=torch.cat(parts);kept=len(indices)
    if kept<128 or kept>=count*.9:return parameters
    selected={k:v.index_select(0,indices) for k,v in parameters.items()}
    node._nurec_background_view_cache=dict(center=center,q=q,half_angle=float(half_angle),versions=versions,
        sources={k:weakref.ref(v) for k,v in parameters.items()},selected=selected)
    if not hasattr(node,'_nurec_background_view_stats'):
        import logging
        logging.getLogger(__name__).info('Private background view: %d/%d points, 8sigma + 2m + angular margin; road/actors unchanged',kept,count)
    node._nurec_background_view_stats=dict(total=count,kept=kept)
    return selected
