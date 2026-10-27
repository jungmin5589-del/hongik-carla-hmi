"""Inference-only scenario workload and conservative static-background compaction.

Read-only checkpoints are retained. Active runtime background parameters may be
compacted once; road and requested actors retain their original parameters.
"""
import logging


def select_render_nodes(model,candidates,edited_tracks):
    wanted=set(edited_tracks.tracks_id)
    kept=[]
    for key in candidates:
        node=model.gaussians_nodes[key]
        tracks=getattr(node,'cuboid_tracks',None)
        dynamic=tracks is not None and getattr(node,'is_static',True) is False
        if dynamic and wanted.isdisjoint(tracks.tracks_id):
            continue
        kept.append(key)
    signature=tuple(kept)
    if getattr(model,'_nurec_lean_selected_nodes',None)!=signature:
        logging.getLogger(__name__).info('Private lean inference: render layers %s from %s',kept,candidates)
        model._nurec_lean_selected_nodes=signature
    return kept



def compact_static_background(model, floor=.005):
    """Drop only negligible-density static background particles, once per load.

    At most the faintest quarter is removed, below a 0.005 opacity ceiling.

    Source checkpoints are read-only. Road and every dynamic actor are excluded.
    Replacing inference parameters releases the removed GPU tensors; there is no
    per-frame gather and no temporal/dynamic feature freezing.
    """
    import torch
    if getattr(model, '_nurec_background_compacted', False):return
    if torch.distributed.is_initialized() and torch.distributed.get_world_size()!=1:return
    node=model.gaussians_nodes.get('background') if isinstance(model.gaussians_nodes,dict) else (
        model.gaussians_nodes['background'] if 'background' in model.gaussians_nodes else None)
    if node is None or getattr(node,'cuboid_tracks',None) is not None:return
    params=node.get_parameters();count=len(params['positions'])
    if count<128:return
    if any(value.ndim==0 or value.shape[0]!=count for value in params.values()):return
    opacity=torch.sigmoid(params['densities'].detach()).reshape(count,-1).amax(1)
    histogram={str(t):int((opacity<t).sum()) for t in [.01,.03,.05,.1,.2]}
    # Bound loss to the faintest quarter, with a strict low-opacity ceiling.
    finite=opacity[torch.isfinite(opacity)]
    if len(finite)!=count:return
    floor=min(floor,float(torch.kthvalue(finite,max(1,count//4)).values))
    indices=torch.nonzero(opacity>=floor,as_tuple=False).flatten()
    if len(indices)<count//2:
        logging.getLogger(__name__).warning('Private background LOD rejected: removed over half the particles')
        model._nurec_background_compacted=True
        return
    if len(indices)<count:
        for key,value in params.items():
            setattr(node,key,torch.nn.Parameter(value.detach().index_select(0,indices),requires_grad=False))
    model._nurec_background_compacted=True
    model._nurec_background_lod=dict(total=count,kept=len(indices),opacity_floor=floor,histogram=histogram)
    logging.getLogger(__name__).info('Private background LOD: %s',model._nurec_background_lod)


def camera_visible_parameters(rendering_data,parameters,model=None):
    """Rejected performance candidate; not invoked by the production runtime.

    Conservatively exclude Gaussian spheres outside the calibrated lens cone.

    Operates on activated, transformed collector output. Four-sigma bounds and
    an extra angular margin preserve silhouettes. No distance or opacity LOD.
    """
    import math
    import torch
    if torch.distributed.is_initialized() and torch.distributed.get_world_size()!=1:
        return parameters
    sensor=rendering_data.sensor_model_parameters[0]
    max_angle=getattr(sensor,'max_angle',None)
    if max_angle is None or not 0.<float(max_angle)<math.pi-.1:
        return parameters
    positions=parameters['positions'];scales=parameters['scales'];count=len(positions)
    if count==0:return parameters
    # The collector applies exp activation; fail open if a different runtime
    # supplies log-scales. Inspect once because this is a model invariant.
    valid_scales=getattr(model,'_nurec_cull_linear_scales',None) if model is not None else None
    if valid_scales is None:
        valid_scales=not bool((scales<0).any())
        if model is not None:model._nurec_cull_linear_scales=valid_scales
    if not valid_scales:return parameters
    camera=rendering_data.poses_tquat_startend[0,0].to(positions)
    q=camera[3:];q=q/torch.linalg.vector_norm(q).clamp_min(1e-8)
    x,y,z,w=q.unbind()
    rotation=torch.stack((
        1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),
        2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),
        2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))).reshape(3,3)
    local=(positions-camera[:3])@rotation
    distance=torch.linalg.vector_norm(local,dim=1).clamp_min(1e-8)
    radius=4.*scales.amax(dim=1)
    angle=torch.atan2(torch.linalg.vector_norm(local[:,:2],dim=1),local[:,2])
    angular_radius=torch.asin((radius/distance).clamp(0.,1.))
    keep=(radius>=distance)|(angle<=float(max_angle)+angular_radius+.12)
    indices=torch.nonzero(keep,as_tuple=False).flatten()
    kept=indices.numel()
    # A nearly empty result is suspicious on the existing driving corridors.
    if kept<max(1,min(128,int(count*.001))):return parameters
    if model is not None:
        stats=dict(total=count,kept=kept,method='calibrated lens cone, 4-sigma bounds and 0.12rad margin')
        if not hasattr(model,'_nurec_cull_stats'):
            logging.getLogger(__name__).info('Private camera culling: %s',stats)
        model._nurec_cull_stats=stats
    if kept==count:return parameters
    return {key:value.index_select(0,indices) if isinstance(value,torch.Tensor)
            and value.ndim>0 and value.shape[0]==count else value
            for key,value in parameters.items()}
