"""Conservative camera visibility for fast traffic; simulation is never culled."""
import math
import numpy as np


def visible_fast_traffic(actors,camera,max_angle,vehicles,protected):
    if max_angle is None or not 0<float(max_angle)<math.pi-.1:return actors
    result=[]
    for actor in actors:
        if actor.track_id in protected or actor.track_id not in vehicles:
            result.append(actor);continue
        p=actor.pose_pair.start_pose.vec
        local=(np.array([p.x,p.y,p.z])-camera[:3,3])@camera[:3,:3]
        radius=float(np.linalg.norm(vehicles[actor.track_id]['size']))/2.+8.
        distance=float(np.linalg.norm(local))
        if distance<=radius:
            result.append(actor);continue
        angle=math.atan2(float(np.linalg.norm(local[:2])),float(local[2]))
        if angle<=float(max_angle)+math.asin(min(1.,radius/distance))+.12:
            result.append(actor)
    return result
