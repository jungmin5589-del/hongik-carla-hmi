"""Deterministic, independent nighttime weaving-car trial. No perception claims.

All positions are in the source-aligned right-handed ENU frame. The bridge
uses this exact cuboid-centre pose for both CARLA and the neural renderer.
"""
import json
import math
import threading
import time
import uuid
from datetime import datetime, timezone

import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from action_outcome import ActionOutcome


class Route:
    def __init__(self, matrices):
        self.matrices = np.asarray(matrices)
        self.points = self.matrices[:, :3, 3]
        self.arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(self.points[:, :2], axis=0), axis=1))]
        self.length = float(self.arc[-1])
        self.rotations = Slerp(self.arc, Rotation.from_matrix(self.matrices[:, :3, :3]))

    def project(self, xy):
        delta = self.points[1:, :2] - self.points[:-1, :2]
        u = np.clip(np.sum((np.asarray(xy) - self.points[:-1, :2]) * delta, axis=1) /
                    np.maximum(np.sum(delta * delta, axis=1), 1e-8), 0, 1)
        closest = self.points[:-1, :2] + u[:, None] * delta
        k = int(np.argmin(np.linalg.norm(closest - xy, axis=1)))
        return float(self.arc[k] + u[k] * (self.arc[k+1] - self.arc[k]))

    def sample(self, distance, lateral=0., yaw_delta=0., height=.75):
        distance = float(np.clip(distance, 0., self.length))
        pose = np.eye(4)
        pose[:3, :3] = self.rotations(distance).as_matrix()
        pose[:3, 3] = [np.interp(distance, self.arc, self.points[:, k]) for k in range(3)]
        pose[:3, 3] += pose[:3, 1] * lateral
        pose[2, 3] += height
        pose[:3, :3] = pose[:3, :3] @ Rotation.from_euler('z', yaw_delta).as_matrix()
        return pose


class Scenario2:
    TRACK_ID = '108'  # Rear-view reconstruction visually checked against four candidates.
    ONSET_SECONDS = 6.
    LEAD_SPEED = 3.0  # m/s; slow nighttime lead car, about 11 km/h.
    BASE_GAP = 14.
    WIDE_GAP = 30.

    def __init__(self, route, event_path):
        self.route = Route(route)
        self.lock = threading.RLock()
        self.events = open(event_path, 'a', encoding='utf-8', buffering=1)
        self.enabled = True
        self.height = .75
        self.half_length = 2.02
        self.reset()

    def log(self, event, **extra):
        self.events.write(json.dumps(dict(event=event, session=self.session,
            utc=datetime.now(timezone.utc).isoformat(), monotonic=time.monotonic(),
            driving_elapsed_s=round(self.elapsed, 4), **extra), ensure_ascii=False) + '\n')

    def reset(self, enabled=None):
        with self.lock:
            if enabled is not None:
                self.enabled = enabled
            self.session = uuid.uuid4().hex[:12]
            self.elapsed = 0.
            self.lead_s = 20.
            self.ego_s = 0.
            self.gap = 16.
            self.desired_gap = self.BASE_GAP
            self.onset = False
            self.onset_monotonic = None
            self.notification_seen = False
            self.dialog_open = False
            self.detail_opened = None
            self.last_action = None
            self.action_complete = False
            self.feedback = ''
            self.horn_count = 0
            self.settle_until = 0.
            self.horn_at = -10.
            self.completed = False
            self.completion_reason = None
            self.outcome = ActionOutcome()
            self.log('trial_ready', enabled=self.enabled, onset_seconds=self.ONSET_SECONDS)

    def advance(self, dt, driving, ego_xy, speed):
        with self.lock:
            self.ego_s = self.route.project(ego_xy)
            if self.enabled and driving and not self.completed:
                self.elapsed += min(max(dt, 0.), .2)
                self.lead_s = min(self.route.length - 8., self.lead_s + self.LEAD_SPEED * min(max(dt, 0.), .2))
                if not self.onset and self.elapsed >= self.ONSET_SECONDS:
                    self.onset = True
                    self.onset_monotonic = time.monotonic()
                    self.log('weaving_started')
            # Bumper-to-bumper along-road distance, not centre distance.
            self.gap = max(0., self.lead_s - self.ego_s - self.half_length - 1.85)
            if self.last_action == 'widen' and not self.action_complete and self.gap >= self.desired_gap - .5:
                self.action_complete = True
                self.feedback = '앞차와의 간격을 넓혔어요. 여유를 두고 주행합니다.'
                self.log('action_completed', action='widen', gap_m=self.gap)
            route_complete = bool(self.enabled and self.lead_s >= self.route.length - 8.01 and
                                  self.gap <= self.desired_gap + 3 and speed < 1.)
            return self.finish_advance(dt, driving, speed, route_complete)

    def finish_advance(self, dt, driving, speed, route_complete):
        if self.outcome.active:
            self.outcome.tick(dt, driving, speed, self)
            if self.outcome.phase == 'complete':
                self.completed = True
                self.completion_reason = 'action_outcome'
                self.feedback = self.outcome.summary
            return 0. if self.outcome.phase in ('stopping', 'complete') else self.target_speed()
        if route_complete and not self.completed:
            self.completed = True
            self.completion_reason = 'route_end'
            self.log('route_completed', ego_s=self.ego_s)
        return self.target_speed()

    def require_action_available(self):
        if self.completed or self.outcome.active:
            raise ValueError('선택한 행동의 결과를 확인하고 있습니다. 현재 대응이 끝난 뒤 다시 선택해 주세요.')

    def target_speed(self):
        with self.lock:
            if not self.enabled:
                return None
            lead_speed = 0. if self.lead_s >= self.route.length - 8.01 else self.LEAD_SPEED
            # A gap request changes the physical ego speed, never the camera/ego pose.
            return max(0., min(30., (lead_speed + .40 * (self.gap - self.desired_gap)) * 3.6))

    def pose(self):
        with self.lock:
            t = max(0., self.elapsed - self.ONSET_SECONDS)
            ramp = min(1., t / 2.) if self.onset else 0.
            # Crosses the lane edge occasionally, without sweeping through both lanes.
            amplitude = 1.20 * ramp
            if self.elapsed < self.settle_until:
                blend = min(1., max(0., self.elapsed - self.horn_at), self.settle_until - self.elapsed)
                blend = blend * blend * (3 - 2 * blend)
                amplitude *= 1. - .82 * blend
            phase = 2 * math.pi * t / 7.
            lateral = amplitude * math.sin(phase)
            lateral_speed = amplitude * (2 * math.pi / 7.) * math.cos(phase)
            yaw = math.atan2(lateral_speed, self.LEAD_SPEED)
            return self.route.sample(self.lead_s, lateral, yaw, self.height), lateral, yaw

    def interaction(self, action, session):
        with self.lock:
            if session != self.session or not self.enabled or not self.onset:
                raise ValueError('현재 알림에서 다시 선택해 주세요.')
            now = time.monotonic()
            if action == 'notification_exposed':
                if not self.notification_seen:
                    self.notification_seen = True
                    self.log(action)
            elif action == 'open':
                if not self.dialog_open:
                    self.dialog_open = True
                    self.detail_opened = now
                    self.log('details_opened', since_onset_s=now - self.onset_monotonic)
            elif action == 'close':
                if self.dialog_open:
                    self.log('details_closed', exposure_s=now - self.detail_opened)
                    self.dialog_open = False
                    self.detail_opened = None
            elif action in ('horn', 'widen', 'maintain'):
                self.require_action_available()
                if not self.dialog_open:
                    raise ValueError('상황 창을 먼저 열어 주세요.')
                self.log('action_selected', action=action, since_onset_s=now - self.onset_monotonic,
                         details_exposure_s=now - self.detail_opened, gap_m=self.gap)
                self.last_action = action
                self.action_complete = action != 'widen'
                if action == 'horn':
                    self.horn_count += 1
                    self.horn_at = self.elapsed
                    self.settle_until = self.elapsed + 4.
                    self.feedback = '경적을 울렸어요. 앞차 반응을 지켜보며 거리를 유지합니다.'
                elif action == 'widen':
                    self.desired_gap = self.WIDE_GAP
                    self.feedback = '서서히 감속해 앞차와의 간격을 넓히고 있어요.'
                else:
                    self.feedback = '현재 주행을 유지하며 앞차 움직임을 지켜봅니다.'
                self.log('action_applied', action=action, target_gap_m=self.desired_gap,
                         feedback=self.feedback, horn_count=self.horn_count)
                self.outcome.begin(action)
            else:
                raise ValueError('Unknown scenario action')
            return self.public()

    def public(self):
        with self.lock:
            _, lateral, yaw = self.pose()
            return dict(id='drowsy_night' if self.enabled else 'free_drive', session=self.session,
                enabled=self.enabled, onset=self.onset, elapsed_s=round(self.elapsed, 2),
                dialog_open=self.dialog_open, action=self.last_action, action_complete=self.action_complete, feedback=self.feedback,
                horn_count=self.horn_count, gap_m=round(self.gap, 1), target_gap_m=self.desired_gap,
                lateral_m=round(lateral, 3), yaw_delta_deg=round(math.degrees(yaw), 2),
                lead_s=round(self.lead_s, 3), completed=self.completed,
                completion_reason=self.completion_reason, outcome=self.outcome.public(),
                state_source='scripted CARLA scenario; not a drowsiness detector')
