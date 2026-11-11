"""Continuous mapped-lane stimulus, paced by actual CARLA simulation time."""
def advance_passing(distance,ego_distance,speed_kph,sim_dt,count,spacing=13.,rear=80.):
    if count<1 or spacing<=0:raise ValueError('Invalid passing traffic corridor')
    cycle=count*spacing
    distance+=max(0.,speed_kph)/3.6*max(0.,sim_dt)
    return ego_distance+(distance-ego_distance+rear)%cycle-rear
