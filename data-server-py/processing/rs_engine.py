"""Rust 6DOF 백엔드(sixdof_rs) 싱글턴.

udp_sender.process_and_send_6dof 의 transform → 회전감쇠 → filter → limiter → 100Hz 보간 송신을
Rust 확장 모듈 `sixdof_rs.Engine` 이 대신한다 (출력은 Python 원본과 비트 단위 동일).

백엔드 선택: 환경변수 SIXDOF_BACKEND
  auto   (기본) sixdof_rs 가 import 되면 Rust, 아니면 기존 Python 파이프라인
  rust          Rust 강제 (모듈 없으면 ImportError)
  python        기존 Python 파이프라인 강제
환경변수 SIXDOF_ACC_PREFILTER: 0(기본, Python 과 동일) | 1(가속도 사전 LPF 사용)
환경변수 SIXDOF_HOLD: 0(기본, 100Hz 선형 보간) | 1(최신 값 즉시 송신 + 100Hz 반복) | 2(100Hz 반복만, 간격 일정)
  ⚠ 1 은 2026-11-08 리그 실측에서 반응이 ~150ms 느려짐(불규칙 패킷 간격). 쓰지 말 것. 2 는 0 과 차이 없음.
시나리오 프로파일은 기존과 같이 SCENARIO=A|B 환경변수로 결정된다.

MotionHouse 패킷 형식: 환경변수 SIXDOF_PACKET
  legacy   (기본) 기존 udp_sender.py 와 바이트 동일한 69B — 현재 리그 튜닝 기준
  official        MotionHouse UserUDP 공식 문서 레이아웃 101B
    SIXDOF_ANGLE=deg2rad (기본) roll/pitch/yaw 를 rad 로 변환 | raw = 값 그대로

sixdof_rs.pyd 는 data-server-py/ 폴더에 둔다(collector 가 그 폴더를 sys.path 에 올림).
"""
import os

_BACKEND = os.environ.get("SIXDOF_BACKEND", "auto").strip().lower()

try:
    if _BACKEND == "python":
        raise ImportError("SIXDOF_BACKEND=python")
    import sixdof_rs as _rs
    ENABLED = True
except ImportError:
    if _BACKEND == "rust":
        raise
    _rs = None
    ENABLED = False

SCENARIO = (os.environ.get("SCENARIO", "A").strip().upper() or "A")

# udp_sender 가 import 시 자기 송신 설정으로 덮어쓴다.
CONFIG = {"host": "127.0.0.1", "port": 10000, "hz": 100.0, "interp": True, "dt": 1.0 / 25,
          "packet": os.environ.get("SIXDOF_PACKET", "legacy").strip().lower() or "legacy",
          "angle": os.environ.get("SIXDOF_ANGLE", "deg2rad").strip().lower() or "deg2rad",
          # condition_accel(±8 클립 + τ0.30/0.18s EMA)은 Python 파이프라인에 없는 단계.
          # 기본 0 = Python 원본과 동일 출력. 1 이면 carla_6dof_link 식 사전 필터 사용.
          "acc_prefilter": os.environ.get("SIXDOF_ACC_PREFILTER", "0").strip() == "1"}
# 1 이면 보간 대신 최신 값을 즉시 송신 + 100Hz 반복(hold). 보간의 ~1 tick 지연 제거.
# (켰을 때만 넘김: hold 인자가 없는 이전 빌드와도 호환)
# 2 이면 hold 하되 즉시 송신 없이 정확한 100Hz 간격만 유지.
_hold = os.environ.get("SIXDOF_HOLD", "0").strip()
if _hold in ("1", "2"):
    CONFIG["hold"] = True
    if _hold == "2":
        CONFIG["hold_now"] = False

_engine = None
_pending_motion_dt = None   # Engine 생성 전에 들어온 transforms.set_dt 값


def get():
    """Engine 을 처음 쓰는 시점에 생성 (CONFIG 반영)."""
    global _engine
    if _engine is None:
        _engine = _rs.Engine(SCENARIO, **CONFIG)
        if _pending_motion_dt is not None:
            _engine.set_motion_dt(_pending_motion_dt)
        print(f"[sixdof_rs] Rust 6DOF 백엔드 사용 (v{_rs.__version__}, 시나리오 {SCENARIO}, "
              f"{CONFIG['host']}:{CONFIG['port']}, "
              f"{'%.0fHz 보간' % CONFIG['hz'] if CONFIG['interp'] else 'tick 즉시송신'}, "
              f"패킷 {_engine.packet_format})")
    return _engine


def set_motion_dt(dt):
    """transforms.set_dt — udp_sender import 중(설정 확정 전)에도 불리므로 Engine 생성을 미룬다."""
    global _pending_motion_dt
    if _engine is None:
        _pending_motion_dt = dt
    else:
        _engine.set_motion_dt(dt)


def reset():
    """transforms.reset_state — Engine 이 아직 없으면 초기 상태이므로 할 일 없음."""
    if _engine is not None:
        _engine.reset()


def close():
    global _engine
    if _engine is not None:
        _engine.close()
        _engine = None
