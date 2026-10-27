"""Explicit render/traffic presets. Native source files are never edited."""
import copy

PRESETS={
    'balanced':dict(quality='balanced',traffic_load='compact',size=(960,540)),
    'standard':dict(quality='high',traffic_load='standard',size=(1280,720)),
}

def traffic_config(config,load='standard'):
    if load not in ('standard','compact'):raise ValueError('Unknown traffic workload')
    result=copy.deepcopy(config)
    if load=='compact':
        result['fast_track_ids']=result['fast_track_ids'][:8]
        protected={result['lead_track_id'],*result['large_track_ids'],*result['fast_track_ids']}
        result['vehicles']={k:v for k,v in result['vehicles'].items() if k in protected}
        result['insert_assets']=[s for s in result.get('insert_assets',[]) if s['id'] in protected]
    result['traffic_load']=load
    return result
