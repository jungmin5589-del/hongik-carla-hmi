"""CARLA road geometry and physical path following; no neural assets required."""
import math
import numpy as np


def driving_lanes(wp):
    """Same-direction lanes, ordered from left to right, with bounded traversal."""
    lanes, seen = [wp], {wp.lane_id}
    for side in ('left', 'right'):
        current = wp
        for _ in range(8):
            other = getattr(current, 'get_'+side+'_lane')()
            if (not other or str(other.lane_type) != 'Driving' or
                    other.lane_id*wp.lane_id <= 0 or other.lane_id in seen):
                break
            lanes.insert(0, other) if side == 'left' else lanes.append(other)
            seen.add(other.lane_id)
            current = other
    return lanes


class HighwayRoute:
    def __init__(self, waypoints):
        self.waypoints = waypoints
        self.points = np.array([[w.transform.location.x, w.transform.location.y,
                                 w.transform.location.z] for w in waypoints])
        self.delta = np.diff(self.points[:, :2], axis=0)
        self.segment_length = np.linalg.norm(self.delta, axis=1)
        if np.any(self.segment_length < .01):
            raise ValueError('Repeated route geometry')
        self.arc = np.r_[0., np.cumsum(self.segment_length)]
        self.length = float(self.arc[-1])
        self.width = float(waypoints[0].lane_width)

    @classmethod
    def build(cls, road_map):
        candidates = [p for p in road_map.generate_waypoints(20)
                      if not p.is_junction and len(driving_lanes(p)) == 4
                      and driving_lanes(p)[1].lane_id == p.lane_id]
        # Town04's ring road. Prefer a straight run with the median on the left.
        candidates.sort(key=lambda p: (p.road_id != 6, p.lane_id != -2, abs(p.s-120)))
        for start in candidates[:12]:
            current, path = start, [start]
            for _ in range(6000):
                options = [q for q in current.next(2.) if len(driving_lanes(q)) == 4]
                if not options:
                    break
                def score(q):
                    turn = abs((q.transform.rotation.yaw-current.transform.rotation.yaw+180)%360-180)
                    return (driving_lanes(q)[1].lane_id != q.lane_id, turn)
                current = min(options, key=score)
                if len(path)>400 and current.transform.location.distance(start.transform.location)<2.5:
                    # Close at the original point, without a camera or vehicle teleport.
                    path.append(start)
                    result = cls(path)
                    if result.segment_length.max()<4.5:
                        return result
                    break
                path.append(current)
        raise RuntimeError('No continuous four-lane Town04 ring route was found.')

    def sample(self, s, offset=0.):
        s = float(s % self.length)
        i = min(len(self.delta)-1, max(0, int(np.searchsorted(self.arc, s, side='right')-1)))
        u = (s-self.arc[i])/self.segment_length[i]
        xyz = (1-u)*self.points[i]+u*self.points[i+1]
        direction = self.delta[i]/self.segment_length[i]
        xyz[:2] += np.array([-direction[1], direction[0]])*offset
        return xyz, math.atan2(direction[1], direction[0])

    def project(self, xy, previous=None):
        xy = np.asarray(xy)
        u = np.clip(np.sum((xy-self.points[:-1,:2])*self.delta, axis=1)/self.segment_length**2, 0, 1)
        points = self.points[:-1,:2]+self.delta*u[:,None]
        distances = np.linalg.norm(points-xy, axis=1)
        if previous is not None:
            # Prevent nearest-segment jumps where roads pass close to one another.
            ds = (self.arc[:-1]-previous+self.length/2)%self.length-self.length/2
            distances[np.abs(ds)>80] = np.inf
        i = int(np.argmin(distances))
        s = float(self.arc[i]+u[i]*self.segment_length[i])
        if previous is not None:
            s = previous+(s-previous+self.length/2)%self.length-self.length/2
        return s, float(distances[i])


def steering(route, distance, offset, transform, speed):
    """Pure pursuit in CARLA's left-handed XY coordinate system."""
    lookahead = max(6., min(17., 5.+speed*.65))
    point, _ = route.sample(distance+lookahead, offset)
    yaw = math.radians(transform.rotation.yaw)
    angle = math.atan2(point[1]-transform.location.y, point[0]-transform.location.x)-yaw
    angle = math.atan2(math.sin(angle), math.cos(angle))
    wheel_angle = math.atan2(2.*2.85*math.sin(angle), lookahead)
    return max(-.75, min(.75, wheel_angle/.58))


def fog_density(elapsed):
    u = min(1., max(0., (elapsed-10.)/5.))
    return 99.*u*u*(3.-2.*u)
