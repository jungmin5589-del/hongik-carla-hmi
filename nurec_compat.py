"""Private compatibility fix for the pinned 26.4 runtime's stale NRend assets.

Called once after an edit transaction, never per RGB frame. No asset is removed.
"""
import gc
import logging


def refresh_nrend(renderable):
    model = renderable._model
    if not model.has_nrend():
        return False
    tracks = model.get_updated_cuboid_tracks()
    ids = list(tracks.tracks_id)
    if len(ids) != len(set(ids)):
        raise RuntimeError('NRend track IDs must be unique after asset editing.')
    # Free the old GPU renderer before allocating the replacement.
    model._nrend_renderer = None
    gc.collect()
    import torch
    torch.cuda.empty_cache()
    model.setup_nrend(track_ids=ids)
    if not model.has_nrend():
        raise RuntimeError('NRend failed to rebuild edited assets; do not serve stale traffic.')
    renderable._nrend.tracks = tracks
    logging.getLogger(__name__).info('Private NRend compatibility refresh: %d tracks, including inserted assets',len(ids))
    return True
