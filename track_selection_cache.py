"""One-entry inference cache for immutable actor parameter selections.

Only selected model parameters are reused; per-frame poses, interpolation,
appearance evaluation and camera rendering remain in the native runtime.
"""
import weakref


def select_track_parameters(node, parameters, tracks_edit):
    import torch
    ids=parameters['gaussian_cuboid_ids']
    cacheable=not node.training and not torch.is_grad_enabled()
    versions=[]
    if cacheable:
        try:
            versions=[(k,v._version) for k,v in parameters.items()]
        except RuntimeError:
            # Inference tensors without mutation counters are never cached.
            cacheable=False
    key=(tuple(node.cuboid_tracks.tracks_id),tuple(tracks_edit.cuboid_tracks.tracks_id),tuple(versions))
    entry=getattr(node,'_nurec_track_selection_cache',None)
    if cacheable and entry is not None and entry[0]==key and all(
            entry[1].get(k,lambda:None)() is v for k,v in parameters.items()):
        return entry[2]
    # Evict before allocating another subset; keep at most one per model.
    node._nurec_track_selection_cache=None
    mask=torch.zeros((node.cuboid_tracks.n_tracks,),dtype=torch.bool,device=ids.device)
    mask[tracks_edit.mapping]=True
    indices=torch.arange(ids.shape[0],device=ids.device)[mask[ids]]
    selected={k:v[indices] for k,v in parameters.items()}
    if cacheable:
        node._nurec_track_selection_cache=(key,{k:weakref.ref(v) for k,v in parameters.items()},selected)
    return selected
