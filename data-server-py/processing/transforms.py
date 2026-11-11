"""
시나리오별 6DOF transforms 자동 디스패처.

SCENARIO 환경변수(A|B)에 따라 transforms_A / transforms_B 를 자동 선택한다.
시나리오 main.py 가 파이프라인 import '전에'
    os.environ['SCENARIO'] = 'A'   # 또는 'B'
를 설정하면, collector → udp_sender → (여기)로 이어지는 import 체인이
해당 시나리오의 프로파일을 적재한다. 미설정 시 'A'(무상태·컴포트 기본).

→ 더 이상 transforms.py 를 손으로 갈아끼울 필요 없음.
  A/B 원본은 transforms_A.py / transforms_B.py 로 공존한다. (수동 swap 폐기)
"""
import os as _os

SCENARIO = (_os.environ.get('SCENARIO', 'A').strip().upper() or 'A')

if SCENARIO == 'B':
    from processing.transforms_B import *          # noqa: F401,F403
    from processing.transforms_B import (          # 명시 재노출 (B 전용 API 포함)
        transform_motion, reset_state, set_dt, is_event_active, trigger_event,
    )
else:
    from processing.transforms_A import *          # noqa: F401,F403
    from processing.transforms_A import transform_motion, reset_state

print(f"[transforms] 프로파일 적재: 시나리오 {SCENARIO}")


# ── Rust 백엔드(sixdof_rs) 사용 시: 시나리오가 부르는 이벤트/DT API 를 Rust Engine 으로 연결 ──
#   (B 수막 시나리오의 trigger_event(case=..)/set_dt 등이 Python 파이프라인 대신 Rust 엔진으로 간다.)
#   SIXDOF_BACKEND=python 이면 ENABLED=False 라 이 블록은 비활성(기존 동작 그대로).
from processing import rs_engine as _rs_engine   # noqa: E402

if _rs_engine.ENABLED:
    def trigger_event(*args, **kwargs):                 # noqa: F811
        if SCENARIO == 'B':
            # B 원본 시그니처: (case, duration=2.0, slip=False, slip_dir=1)
            names = ("case", "duration", "slip", "slip_dir")
        else:
            # A 원본 시그니처: (duration=None)
            names = ("duration",)
        kwargs.update(zip(names, args))
        _rs_engine.get().trigger_event(**kwargs)

    def stop_event():                                   # noqa: F811
        _rs_engine.get().stop_event()

    def is_event_active():                              # noqa: F811
        return _rs_engine.get().is_event_active()

    def set_dt(dt):                                     # noqa: F811  (이벤트 clock DT)
        _rs_engine.set_motion_dt(dt)

    def reset_state():                                  # noqa: F811
        _rs_engine.reset()
