"""Keep NuRec's independent RGB output while avoiding unused UE drawing."""


def renderer_is_nrend(config):
    # Current servers report the unified key; older ones expose the legacy flag.
    name = str(config.get('renderer', '')).lower()
    if name:
        return name == 'nrend'
    return str(config.get('enable_nrend', '')).lower() == 'true'


def renderer_matches(config, requested):
    name = str(config.get('renderer', '')).lower()
    if requested == 'gsplat-native':
        return name == 'gsplat' and config.get('nurec_private_camera_mode') == 'native'
    if requested == 'gsplat':
        return name == 'gsplat' or (not name and str(config.get('use_gsplat', '')).lower() == 'true')
    if requested == 'nrend':
        return renderer_is_nrend(config)
    return name in ('', 'default', 'trained') and not renderer_is_nrend(config)


def enable_physics_only(world):
    settings = world.get_settings()
    if settings.synchronous_mode:
        raise RuntimeError('NuRec requires the existing asynchronous world settings.')
    if any(actor.type_id.startswith('sensor.camera.') for actor in world.get_actors()):
        raise RuntimeError('A CARLA GPU camera needs rendering; left its settings unchanged.')
    previous = settings.no_rendering_mode
    if not previous:
        settings.no_rendering_mode = True
        world.apply_settings(settings)
    return previous
