"""A finite real-route stop/creep trial; no looping, video replay, or ego teleport."""
import math
import time
import numpy as np
from scenario2 import Scenario2


class Congestion(Scenario2):
    TYPE_ID = 'congestion_long'
    ONSET_SECONDS = 20.
    BASE_GAP = 10.
    WIDE_GAP = 24.
    SUPPRESS_OTHER_TRAFFIC = False

    def __init__(self, route, event_path, track_id, duration=450):
        self.TRACK_ID = str(track_id)
        self.duration = duration
        super().__init__(route, event_path)

    def reset(self, enabled=None):
        super().reset(enabled)
        with self.lock:
            # Rest-to-rest speed envelope with smooth recurring queue waves.
            self.times = np.linspace(0., self.duration, int(self.duration*10)+1)
            t = self.times
            cycle = (t % 55.) / 55.
            # 12 s stopped, gradual start, moving queue, gradual stop per wave.
            ramp = np.clip((cycle-.22)/.16, 0., 1.)
            down = np.clip((1.-cycle)/.18, 0., 1.)
            envelope = (ramp*ramp*(3.-2.*ramp)) * (down*down*(3.-2.*down))
            envelope *= np.clip((self.duration-10.-t)/8., 0., 1.)
            # Begin with an initial gentle departure before queueing.
            envelope[:101] = .45*np.sin(np.linspace(0., math.pi, 101))**2
            distance = np.r_[0., np.cumsum((envelope[:-1]+envelope[1:])*.05)]
            travel = max(0., self.route.length-10.-self.lead_s)
            self.positions = self.lead_s + distance * travel / distance[-1]
            self.speeds = envelope * travel / distance[-1]
            self.lead_speed = 0.
            self.log('congestion_schedule_ready', duration_s=self.duration,
                     lead_end_s=float(self.positions[-1]), no_loop=True)

    def set_duration(self, seconds):
        if seconds not in (300, 450, 600):
            raise ValueError('체험 시간은 5분, 7분 30초, 10분 중 선택해 주세요.')
        self.duration = seconds

    def advance(self, dt, driving, ego_xy, speed):
        with self.lock:
            self.ego_s = self.route.project(ego_xy)
            if self.enabled and driving and not self.completed:
                self.elapsed += min(max(dt, 0.), .2)
                self.lead_s = float(np.interp(self.elapsed, self.times, self.positions))
                self.lead_speed = float(np.interp(self.elapsed, self.times, self.speeds))
                if not self.onset and self.elapsed >= self.ONSET_SECONDS:
                    self.onset = True
                    self.onset_monotonic = time.monotonic()
                    self.log('congestion_started')
            self.gap = max(0., self.lead_s-self.ego_s-self.half_length-1.85)
            if self.last_action == 'widen' and not self.action_complete and self.gap >= self.desired_gap-.5:
                self.action_complete = True
                self.feedback = '앞차와의 간격을 넓혔어요. 여유를 두고 따라갑니다.'
                self.log('action_completed', action='widen', gap_m=self.gap)
            complete = bool(self.enabled and self.elapsed >= self.duration and speed < 1.
                            and abs(self.gap-self.desired_gap) < 3.)
            return self.finish_advance(dt, driving, speed, complete)

    def target_speed(self):
        if not self.enabled:
            return None
        return max(0., min(25., (self.lead_speed+.35*(self.gap-self.desired_gap))*3.6))

    def pose(self):
        with self.lock:
            return self.route.sample(self.lead_s, height=self.height), 0., 0.

    def public(self):
        with self.lock:
            result = super().public()
            result.update(id='congestion_long', duration_s=self.duration,
                          remaining_s=round(max(0., self.duration-self.elapsed)),
                          lead_speed_kph=round(self.lead_speed*3.6, 1),
                          state_source='scripted congestion on a measured finite route; not perception')
            return result
