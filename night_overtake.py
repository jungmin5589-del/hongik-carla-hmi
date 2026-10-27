"""Explicit left-overtake branch: physical ego contact plus scripted pile-up.

This is a predetermined experiment branch, never an autonomous risk prediction.
All added traffic uses native editable tracks also present as CARLA proxies.
"""
import math
import time

import numpy as np

from scenario2 import Scenario2


def ease(value):
    value = min(1., max(0., value))
    return value * value * (3. - 2. * value)


class NightOvertakeScenario(Scenario2):
    OVERTAKE_TRIAL = True
    LEFT_LATERAL = 3.15
    RUNOUT = 50.
    FRONT_GAP = 7.
    REAR_CLEARANCE = 6.5
    IMPACT_YAW = .14

    def reset(self, enabled=None):
        with self.lock:
            super().reset(enabled)
            self.crash_phase = 'idle'
            self.crash_elapsed = self.crash_clock = 0.
            self.crash_seen = set()
            self.physical_contacts = []
            self.primary_verified = False
            self.ego_lateral = 0.
            self.cut_from = None
            self.contact_lead_s = None
            self.contact_lead_lateral = None
            self.rear_s = self.lead_s - 24.
            self.front_s = self.lead_s + self.FRONT_GAP
            self.crash_roles = getattr(self, 'crash_roles', {})
            self.crash_dimensions = getattr(self, 'crash_dimensions', {})

    def configure_crash_traffic(self, candidates):
        """Only renderer-catalog cars with matching collision proxies are eligible."""
        with self.lock:
            asset_ids = {spec['id'] for spec in getattr(self, 'crash_asset_specs', [])}
            cars = sorted((row for row in candidates if row['id'] != self.TRACK_ID
                           and (not asset_ids or row['id'] in asset_ids)
                           and row['kind'] == 'automobile'
                           and 3.2 <= row['length'] <= 6.0 and 1.3 <= row['width'] <= 2.6
                           and 1.0 <= row['height'] <= 2.5), key=lambda row: row['id'])
            self.crash_roles = dict(zip(('front', 'rear'), (row['id'] for row in cars[:2])))
            self.crash_dimensions = {row['id']: row for row in cars[:2]}

    def overtake_unavailable_reason(self):
        if len(self.crash_roles) != 2:
            return '추월 장면에 필요한 주변 차량을 준비하지 못했습니다.'
        if self.route.length - self.ego_s < self.RUNOUT:
            return '구간 끝이 가까워 추월을 시작할 수 없습니다.'
        return ''

    @property
    def crash_active(self):
        return self.crash_phase != 'idle'

    @property
    def crash_brake(self):
        return self.crash_phase in ('primary_impact', 'secondary_impact', 'aftermath', 'failed')

    def set_phase(self, phase):
        self.crash_phase, self.crash_clock = phase, 0.
        self.log('overtake_stage', stage=phase, predetermined_experiment=True)

    def acknowledge_crash_frame(self, session, phase):
        with self.lock:
            if (phase in ('primary_impact','secondary_impact','aftermath') and session == self.session
                    and phase == self.crash_phase and phase not in self.crash_seen):
                self.crash_seen.add(phase)
                self.log('overtake_frame_rendered', stage=phase,
                         measurement='decoded renderer frame; not participant gaze')

    def on_collision(self, role, impulse):
        with self.lock:
            if not self.crash_active or role not in ('lead', 'front', 'rear'):
                return
            if any(contact['role']==role for contact in self.physical_contacts):
                return
            self.physical_contacts.append(dict(role=role, impulse=float(impulse)))
            self.log('carla_collision_observed', role=role, impulse=float(impulse))
            if not self.crash_brake and role == 'lead':
                self.primary_verified = True
                self.contact_lead_s = self.lead_s
                self.contact_lead_lateral = self.pose()[1]
                self.set_phase('primary_impact')
                self.feedback = '추월 중 앞차와 충돌했습니다. 차량을 정지하고 있습니다.'

    def interaction(self, action, session):
        if action != 'overtake':
            return super().interaction(action, session)
        with self.lock:
            if session != self.session or not self.enabled or not self.onset or not self.dialog_open:
                raise ValueError('현재 상황 창에서 대응 방법을 선택해 주세요.')
            self.require_action_available()
            reason = self.overtake_unavailable_reason()
            if reason:
                raise ValueError(reason)
            self.last_action, self.action_complete = 'overtake', False
            self.cut_from = self.pose()[1:]
            self.rear_s = max(0., self.ego_s - 24.)
            self.front_s = min(self.route.length - 8., self.lead_s + self.FRONT_GAP)
            self.set_phase('pulling_out')
            self.feedback = '왼쪽 차로로 추월을 시도하고 있습니다.'
            self.log('action_selected', action='overtake', direction='left',
                     since_onset_s=time.monotonic()-self.onset_monotonic,
                     details_exposure_s=time.monotonic()-self.detail_opened,
                     predetermined_experiment=True)
            self.log('action_applied',action='overtake',direction='left',feedback=self.feedback)
            self.outcome.begin('overtake')
            return self.public()

    def advance(self, dt, driving, ego_xy, speed):
        if not self.crash_active:
            result = super().advance(dt, driving, ego_xy, speed)
            with self.lock:
                self.rear_s = max(0., self.ego_s - 24.)
                self.front_s = min(self.route.length - 8., self.lead_s + self.FRONT_GAP)
            return result
        with self.lock:
            self.ego_s = self.route.project(ego_xy)
            centre = self.route.sample(self.ego_s, height=0.)
            self.ego_lateral = float(np.dot(np.asarray(ego_xy) - centre[:2, 3], centre[:2, 1]))
            if not driving or self.completed:
                return self.target_speed()
            step = min(max(dt, 0.), .2) if driving and not self.completed else 0.
            self.elapsed += step
            self.crash_elapsed += step
            self.crash_clock += step
            if not self.crash_brake:
                self.lead_s = min(self.route.length - 8., self.lead_s + self.LEAD_SPEED * step)
                self.rear_s = min(self.route.length - 8., self.rear_s + 6. * step)
                self.front_s = min(self.route.length - 8., self.front_s + self.LEAD_SPEED * step)
            if self.crash_phase == 'pulling_out' and self.crash_clock >= 2.6:
                self.set_phase('closing')
            self.gap = max(0., self.lead_s - self.ego_s - self.half_length - 1.85)
            if self.crash_phase == 'closing' and self.gap <= 4. and self.ego_lateral >= 2.:
                self.cut_from = super().pose()[1:]
                self.set_phase('cut_in')
                self.feedback = '추월 중 앞 차량이 왼쪽 차로로 들어오고 있습니다.'
            if self.crash_phase == 'primary_impact':
                # The rear car approaches from its last shown position, no spawn at impact.
                rear_target = max(0., self.ego_s - self.REAR_CLEARANCE)
                self.rear_s = min(rear_target, self.rear_s + 9. * step)
                self.lead_s = self.contact_lead_s + 2.5 * ease(self.crash_clock / 1.5)
                if (self.crash_clock >= 1.5 and self.rear_s >= rear_target - .01
                        and 'primary_impact' in self.crash_seen):
                    self.set_phase('secondary_impact')
                    self.feedback = '뒤따르던 차량까지 엉키며 차로가 막혔습니다. 정지 상태를 유지합니다.'
                    self.log('scripted_secondary_impact', physical_contact_verified=False)
            if (self.crash_phase == 'secondary_impact' and self.crash_clock >= 2.
                    and 'secondary_impact' in self.crash_seen):
                self.set_phase('aftermath')
            if self.crash_phase == 'aftermath' and 'aftermath' in self.crash_seen:
                self.action_complete = True
            if ((self.crash_phase in ('pulling_out', 'closing') and self.crash_elapsed > 25.)
                    or (self.crash_phase == 'cut_in' and self.crash_clock > 4.)):
                self.set_phase('failed')
                self.action_complete = True
                self.feedback = '추월 장면의 접촉을 확인하지 못해 정지합니다.'
            # Preserve the physical stopping and full result-observation contract.
            return self.finish_advance(dt, driving, speed, False)

    def target_speed(self):
        with self.lock:
            if not self.crash_active:
                return super().target_speed()
            return 0. if self.crash_brake else 22. if self.crash_phase == 'pulling_out' else 30.

    def steering_target(self, lookahead):
        with self.lock:
            lateral = self.LEFT_LATERAL * ease(self.crash_clock / 2.6) if self.crash_phase == 'pulling_out' else self.LEFT_LATERAL
            return self.route.sample(self.ego_s + lookahead, lateral=lateral, height=0.)[:3, 3]

    def pose(self):
        with self.lock:
            if not self.crash_active or self.crash_phase in ('pulling_out', 'closing', 'failed'):
                return super().pose()
            if self.crash_phase == 'cut_in':
                u = ease(self.crash_clock / 1.2)
                lateral = self.cut_from[0] * (1. - u) + self.LEFT_LATERAL * u
                yaw = self.cut_from[1] * (1. - u) + self.IMPACT_YAW * math.sin(math.pi * min(1., self.crash_clock / 1.2))
            else:
                u = ease(self.crash_clock / 1.5) if self.crash_phase == 'primary_impact' else 1.
                lateral = self.contact_lead_lateral * (1. - u) + 2.35 * u
                yaw = self.IMPACT_YAW * u
            return self.route.sample(self.lead_s, lateral, yaw, self.height), lateral, yaw

    def traffic_poses(self):
        with self.lock:
            poses = {self.TRACK_ID: self.pose()[0]}
            if not self.enabled or len(self.crash_roles) != 2:
                return poses
            yaw_front = -self.IMPACT_YAW * ease(self.crash_clock / 1.5) if self.crash_phase == 'primary_impact' else -self.IMPACT_YAW if self.crash_brake else 0.
            yaw_rear = -self.IMPACT_YAW * ease(self.crash_clock / 2.) if self.crash_phase == 'secondary_impact' else -self.IMPACT_YAW if self.crash_phase == 'aftermath' else 0.
            for role, s, yaw in (('front', self.front_s, yaw_front), ('rear', self.rear_s, yaw_rear)):
                track = self.crash_roles[role]
                poses[track] = self.route.sample(s, self.LEFT_LATERAL, yaw,
                                               self.crash_dimensions[track]['height'] / 2.)
            return poses

    def public(self):
        with self.lock:
            result = super().public()
            result['overtake'] = dict(available=not bool(self.overtake_unavailable_reason()),
                unavailable_reason=self.overtake_unavailable_reason(), direction='left')
            result['crash'] = dict(phase=self.crash_phase, elapsed_s=round(self.crash_elapsed, 3),
                stage_elapsed_s=round(self.crash_clock, 3), primary_collision_verified=self.primary_verified,
                physical_contacts=len(self.physical_contacts), rendered_stages=sorted(self.crash_seen),
                scripted=True, vehicles_in_scene=4, source='predetermined experiment; CARLA contact plus scripted secondary motion')
            return result
