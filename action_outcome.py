"""Observe a requested action before ending a trial; clocks use live driving time."""


class ActionOutcome:
    OBSERVE_SECONDS = 12.
    APPLY_TIMEOUT = 45.

    def __init__(self):
        self.action = None
        self.phase = 'idle'
        self.elapsed = self.observed = self.stopped = 0.
        self.status = None
        self.summary = ''

    @property
    def active(self):
        return self.phase != 'idle'

    def begin(self, action):
        if self.active:
            raise ValueError('선택한 행동의 결과를 확인하고 있습니다. 새 주행에서 다시 선택해 주세요.')
        self.action, self.phase = action, 'applying'

    def tick(self, dt, driving, speed, trial):
        if not self.active or self.phase == 'complete' or not driving:
            return
        step = min(max(dt, 0.), .2)
        self.elapsed += step
        if self.phase == 'applying':
            ready = trial.action_complete
            if self.action == 'stop_request':
                ready = trial.gap >= trial.desired_gap - .5
            if ready or self.elapsed >= self.APPLY_TIMEOUT:
                if self.action == 'overtake':
                    self.status = 'collision' if ready and trial.primary_verified else 'unfulfilled'
                else:
                    self.status = 'partial' if self.action == 'stop_request' else 'achieved' if ready else 'unfulfilled'
                self.summary = self.describe(trial)
                self.phase = 'observing'
                trial.log('outcome_observation_started', action=self.action, status=self.status,
                          gap_m=trial.gap, speed_kph=speed, summary=self.summary)
        elif self.phase == 'observing':
            # A distance request must remain satisfied throughout the result view.
            if self.action in ('widen', 'stop_request') and self.status != 'unfulfilled' and trial.gap < trial.desired_gap - 1.5:
                self.phase = 'applying'
                self.observed = 0.
                return
            self.observed += step
            if self.observed >= self.OBSERVE_SECONDS:
                self.phase = 'stopping'
                trial.log('outcome_observed', action=self.action, observed_s=self.observed)
        elif self.phase == 'stopping':
            self.stopped = self.stopped + step if speed < .5 else 0.
            if self.stopped >= 1.:
                self.phase = 'complete'
                trial.log('outcome_trial_completed', action=self.action, status=self.status,
                          speed_kph=speed, summary=self.summary)

    def describe(self, trial):
        if self.action == 'overtake':
            if self.status == 'collision':
                return '추월 중 앞차와 충돌한 뒤 주변 차량이 엉키며 차로가 막혔습니다. 차량을 정지하고 사고 상황을 확인했습니다.'
            if trial.primary_verified:
                return '앞차와의 충돌은 감지했지만 사고 결과 장면의 표시를 완료하지 못해 주행을 중지했습니다.'
            return '추월 장면에서 차량 접촉을 확인하지 못해 주행을 중지했습니다. 충돌 완료로 기록하지 않습니다.'
        if self.action == 'stop_request':
            return '정차 공간이 확인되지 않아 갓길 정차는 실행하지 않았습니다. 감속하며 앞차 간격을 확보하는 대응을 확인했습니다.' if trial.gap >= trial.desired_gap - .5 else '정차 공간이 확인되지 않았으며 요청한 간격 확보도 완료되지 않았습니다. 정차 요청이 완료된 상태는 아닙니다.'
        if self.status == 'unfulfilled':
            if self.action=='highbeam':return '상향등 점멸 화면의 완료를 확인하지 못했습니다. 점멸이 완료됐다고 표시하지 않습니다.'
            return '요청한 차간 거리까지 확보하지 못했습니다. 실제 감속과 앞차 간격의 변화를 확인했습니다.'
        if self.action=='highbeam':
            return '상향등을 두 번 켰다가 껐습니다. 앞차와 주변 차량의 흐름은 계속되어 정체가 해소되지는 않았습니다.'
        if self.action == 'widen':
            return f'감속해 앞차와 약 {trial.desired_gap:g}m 간격을 확보하고 유지했습니다.'
        if self.action == 'horn':
            if getattr(trial, 'TYPE_ID', '') == 'congestion_long':
                if hasattr(trial,'FAST_SPEED'):
                    return '경적을 한 번 울렸습니다. 앞차와 오른쪽 대형차는 저속 흐름을 유지했고 왼쪽의 빠른 차량도 계속 지나갔습니다.'
                return '경적을 한 번 울렸습니다. 앞차의 정지와 출발은 계속되어 정체가 해소되지는 않았습니다.'
            return '경적을 한 번 울린 뒤 앞차의 흔들림이 잠시 줄었다가 다시 나타나는 반응을 확인했습니다.'
        if self.action == 'inspect':
            return '현재 속도와 앞차 간격을 확인했습니다. 감속과 거리 유지 주행은 계속되었습니다.'
        return '추가 조작 없이 앞차를 따라 현재 주행과 거리 유지가 계속되는 모습을 확인했습니다.'

    def public(self):
        return dict(action=self.action, phase=self.phase, status=self.status, summary=self.summary,
                    observed_s=round(self.observed, 2), observe_s=self.OBSERVE_SECONDS,
                    elapsed_s=round(self.elapsed, 2),
                    message=('추월 시도 중 충돌이 발생해 주행 주행이 종료되었습니다.' if self.action == 'overtake' and self.status == 'collision'
                             else '요청한 대응을 마쳤습니다. 주변 상황을 확인하고 있습니다.') if self.phase == 'complete' else '')
