"""Straight ego, a lead straddling the two-lane boundary, no crash branch."""
import math
import numpy as np

from scenario2 import Scenario2


def recorded_track_height(route, aligned_poses):
    """Keep the native vehicle at its measured height relative to the rig route."""
    heights=[]
    for pose in aligned_poses:
        distance=route.project(pose[:2,3])
        if not .1<distance<route.length-.1:continue
        reference=route.sample(distance,height=0.)
        if np.linalg.norm(pose[:2,3]-reference[:2,3])<12.:
            heights.append(float(pose[2,3]-reference[2,3]))
    if len(heights)<3:raise RuntimeError('Native lead grounding could not be calibrated.')
    height=float(np.median(heights))
    if not -1.<height<2.:raise RuntimeError('Native lead grounding is outside the expected envelope.')
    return height


class BoundaryWeaving(Scenario2):
    TRACK_ID = '108'
    STRAIGHT_TRIAL = True
    BASE_GAP = 11.
    WIDE_GAP = 28.
    # The recorded ego is in the left lane; the neighbouring lane is on its right.
    BOUNDARY = -1.8
    AMPLITUDE = .65
    PERIOD = 10.5

    def pose(self):
        with self.lock:
            t = max(0., self.elapsed - self.ONSET_SECONDS)
            u = min(1., t / 5.) if self.onset else 0.
            ramp = u**3 * (10. - 15.*u + 6.*u*u)
            ramp_speed = 6.*u*u*(1.-u)**2 if 0.<u<1. else 0.
            scale, scale_speed = 1., 0.
            if self.elapsed < self.settle_until:
                blend = min(1., max(0., self.elapsed-self.horn_at), self.settle_until-self.elapsed)
                blend_speed = 1. if self.elapsed-self.horn_at<1. else -1. if self.settle_until-self.elapsed<1. else 0.
                scale = 1. - .82 * blend * blend * (3. - 2. * blend)
                scale_speed = -.82*6.*blend*(1.-blend)*blend_speed
            phase = 2. * math.pi * t / self.PERIOD
            secondary = 2. * math.pi * t / 6.7
            oscillation = .8*math.sin(phase)+.2*math.sin(secondary)
            oscillation_speed = .8*(2.*math.pi/self.PERIOD)*math.cos(phase)+.2*(2.*math.pi/6.7)*math.cos(secondary)
            wave = self.BOUNDARY + self.AMPLITUDE*scale*oscillation
            lateral = ramp * wave
            velocity = ramp_speed*wave+ramp*self.AMPLITUDE*(scale_speed*oscillation+scale*oscillation_speed)
            # Match heading to the derivative of the path, rather than sliding
            # laterally with an independently clamped body heading.
            yaw = math.atan2(velocity, self.LEAD_SPEED)
            return self.route.sample(self.lead_s, lateral, yaw, self.height), lateral, yaw

    def public(self):
        with self.lock:
            result = super().public()
            result.update(layout='two_lane_boundary_weaving', ego_path='same_lane_following',
                lane_boundary_m=self.BOUNDARY, state_source='scripted unstable-driving stimulus; not intoxication detection')
            return result
