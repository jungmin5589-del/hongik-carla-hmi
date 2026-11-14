"""CARLA road geometry and physical path following; no neural assets required."""
import math
from bisect import bisect_left,bisect_right
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
        self._arc_scalar=tuple(float(x) for x in self.arc)
        self._segments=tuple((float(p[0]),float(p[1]),float(d[0]),float(d[1]),float(length),float(at)) for p,d,length,at in zip(self.points,self.delta,self.segment_length,self.arc))

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
        # Small local scalar search: array operations over the full ring release
        # the GIL repeatedly and can starve the controller under RGB callbacks.
        # Preserve the original 80 m continuity window and unwrapped lap count.
        x,y=float(xy[0]),float(xy[1]);arc=self._arc_scalar
        if previous is None:
            ranges=[range(len(self._segments))]
        else:
            centre=float(previous%self.length);lo=centre-80.;hi=centre+80.
            ranges=[]
            if lo<0:ranges.append(range(bisect_left(arc,self.length+lo),len(self._segments)))
            if hi>=self.length:ranges.append(range(0,bisect_right(arc,hi-self.length)))
            ranges.append(range(bisect_left(arc,max(0.,lo)),min(len(self._segments),bisect_right(arc,min(self.length,hi)))))
        best=float('inf');best_s=0.
        for candidates in ranges:
            for i in candidates:
                px,py,dx,dy,length,at=self._segments[i]
                u=max(0.,min(1.,((x-px)*dx+(y-py)*dy)/(length*length)))
                ex=px+dx*u-x;ey=py+dy*u-y;distance=ex*ex+ey*ey
                if distance<best:best=distance;best_s=at+u*length
        if previous is not None:best_s=previous+(best_s-previous+self.length/2)%self.length-self.length/2
        return float(best_s),math.sqrt(best)



def steering(route, distance, offset, transform, speed, geometry=None):
    """Pure pursuit in CARLA's left-handed XY coordinate system."""
    lookahead = max(6., min(17., 5.+speed*.65))
    point, _ = route.sample(distance+lookahead, offset)
    yaw = math.radians(transform.rotation.yaw)
    geometry=geometry or dict(wheelbase=2.85,rear_offset=0.,max_steer=.58)
    rear=geometry['rear_offset']
    dx=point[0]-transform.location.x-rear*math.cos(yaw)
    dy=point[1]-transform.location.y-rear*math.sin(yaw)
    angle = math.atan2(dy,dx)-yaw
    angle = math.atan2(math.sin(angle), math.cos(angle))
    wheel_angle = math.atan2(2.*geometry['wheelbase']*math.sin(angle), max(1.,math.hypot(dx,dy)))
    curve=geometry.get('steering_curve',[])
    # The UE4 PhysX steering table uses km/h (verified in the local engine source).
    scale=float(np.interp(speed*3.6,[p[0] for p in curve],[p[1] for p in curve])) if curve else 1.
    return max(-.75, min(.75, wheel_angle/(geometry['max_steer']*max(.1,scale))))


def curve_speed_limit(route,distance,offset,preferred):
    """Keep the requested straight speed; brake progressively before tight bends."""
    limit=max(0.,preferred)/3.6
    for ahead in (0.,20.,40.,60.,90.,120.):
        a,ya=route.sample(distance+ahead-3.,offset);b,yb=route.sample(distance+ahead+3.,offset)
        change=abs((yb-ya+math.pi)%(2*math.pi)-math.pi)
        curvature=change/max(.1,float(np.linalg.norm(b[:2]-a[:2])))
        if curvature>1e-5:
            future=math.sqrt(3./curvature)
            limit=min(limit,math.sqrt(future*future+2.*2.3*ahead))
    return limit*3.6


def fog_density(elapsed):
    u = min(1., max(0., (elapsed-10.)/5.))
    return 99.*u*u*(3.-2.*u)
