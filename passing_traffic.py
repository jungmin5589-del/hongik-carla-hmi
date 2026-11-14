"""Continuous mapped-lane stimulus, paced by actual CARLA simulation time."""
def advance_passing(distance,ego_distance,speed_kph,sim_dt,count,spacing=13.,rear=80.):
    if count<1 or spacing<=0:raise ValueError('Invalid passing traffic corridor')
    cycle=count*spacing
    distance+=max(0.,speed_kph)/3.6*max(0.,sim_dt)
    return ego_distance+(distance-ego_distance+rear)%cycle-rear


def recycle_destination(distance, ego_distance, count, occupied, spacing=13., rear=80.):
    """Recycle only beyond the forward corridor; never move visible nearby cars.

    Normal motion is provided by CARLA vehicle physics, not framewise transforms.
    Keep a full-car safety gap at the off-screen insertion point.
    """
    if count < 1 or spacing <= 0:
        raise ValueError('Invalid passing traffic corridor')
    cycle=count*spacing
    if distance-ego_distance <= cycle-rear:
        return None
    destination=ego_distance-rear+(distance-ego_distance+rear)%cycle
    # A delayed sample must not wrap a car back into the visible front corridor.
    if destination > ego_distance-60.:return None
    if any(abs(other-destination)<9. for other in occupied):
        return None
    return destination
