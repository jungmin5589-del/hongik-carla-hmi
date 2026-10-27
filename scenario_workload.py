"""Keep every study stimulus; omit unrelated physics proxies in lean trials."""


def required_proxy_ids(scenario, workload='essential', include_all=False):
    config=getattr(scenario,'config',None)
    if isinstance(config,dict) and 'vehicles' in config:
        return set(config['vehicles'])
    if (include_all or workload=='full' or not scenario.enabled
            or getattr(scenario,'OVERTAKE_TRIAL',False)
            or not getattr(scenario,'SUPPRESS_OTHER_TRAFFIC',True)):
        return None
    return {scenario.TRACK_ID}
