"""
역할 : 가공된 데이터를 6DOF로 UDP 전송.

A/B 양쪽 transforms/filters 모듈과 호환되도록 defensive 하게 작성:
  - 시나리오 A (답답함) : transform_motion(accel, rot)            , filters.apply(raw)
  - 시나리오 B (수막)    : transform_motion(accel, rot, speed)     , filters.apply(raw, is_event)
                          + set_dt / is_event_active

processing/ 폴더의 transforms.py 와 filters.py 를 A↔B 로 갈아끼우면
udp_sender 는 그대로 두고 자동으로 그쪽 파이프라인을 따라감.

2026-11-08 (홍익 CARLA 시나리오 앱 연동):
  - 환경변수 SIXDOF_UDP_HOST / SIXDOF_UDP_PORT / SIXDOF_CSV / SIXDOF_PRINT_EVERY (기본값은 기존 동작)
  - reset_pipeline() : 새 ego 로 바뀔 때 필터·리미터 상태 초기화
  - send_neutral()   : 마지막 6축 값 → 0 으로 램프다운 후 중립 패킷 (시나리오 종료·오류 시)
"""
import socket
import struct
import inspect
import csv
import os
import datetime
import atexit
import time

from processing.transforms import transform_motion, reset_state
from processing.filters import (
    apply as apply_filter,
    velocity_limiter,
    reset_filter,
)

# ── B 전용 API 옵셔널 import ──────────────────────────────────────
try:
    from processing.transforms import set_dt as _set_dt
except ImportError:
    def _set_dt(_dt):       # A 는 stateless
        pass

try:
    from processing.transforms import is_event_active as _is_event_active
except ImportError:
    def _is_event_active():  # A 는 이벤트 분기 없음
        return False

# ── transform_motion / apply_filter 시그니처 자동 감지 ─────────────
_TM_PARAMS = len(inspect.signature(transform_motion).parameters)
_AF_PARAMS = len(inspect.signature(apply_filter).parameters)


def _call_transform(accel, rot, speed_ms):
    if _TM_PARAMS >= 3:
        return transform_motion(accel, rot, speed_ms)
    return transform_motion(accel, rot)


def _call_apply(motion, is_event):
    if _AF_PARAMS >= 2:
        return apply_filter(motion, is_event=is_event)
    return apply_filter(motion)


# ── 송신 설정 ────────────────────────────────────────────────────
UDP_IP   = os.environ.get("SIXDOF_UDP_HOST", "127.0.0.1")
UDP_PORT = int(os.environ.get("SIXDOF_UDP_PORT", "10000"))
DT       = 1.0 / 25       # 25Hz (collector fixed_delta_seconds=0.02 면 1/50 권장)
PRINT_EVERY = int(os.environ.get("SIXDOF_PRINT_EVERY", "1"))   # N프레임마다 콘솔 1줄, 0 이면 끔

# ── 회전 상황 멀미 저감 ───────────────────────────────────────────
# 회전교차로/급커브(높은 yaw rate)에서 6DOF 진폭을 크게 줄여 멀미 완화.
# yaw rate 는 collector 가 보내는 angular_velocity.z (CARLA: deg/s) 사용.
TURN_YAW_RATE_THRESH = 5.0    # deg/s, 이 이상이면 '회전 중'으로 판정
TURN_COMFORT_SCALE   = 0.75   # v18: 0.45→0.75 회전 중 감쇠 완화 (리그 #2 — 커브 회전감 살림)
_TURN_RAMP           = 0.12   # 스케일 전환 보간율 (프레임당 — 급변 방지)
_turn_scale          = 1.0    # 현재 적용 중인 진폭 배율 (램프 상태)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ── 모듈 로드 시 1회 초기화 ──────────────────────────────────────
_set_dt(DT)
reset_state()
reset_filter()

_KEYS = ("surge", "sway", "heave", "roll", "pitch", "yaw")
_prev_limited = {k: 0.0 for k in _KEYS}
_frame_count = 0
send_fail_count = 0

# ── CSV 로깅 ─────────────────────────────────────────────────────
CSV_ENABLED = os.environ.get("SIXDOF_CSV", "1") != "0"   # SIXDOF_CSV=0 이면 비활성화
_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs",
)
os.makedirs(_LOG_DIR, exist_ok=True)
_csv_path = os.path.join(
    _LOG_DIR,
    f"6dof_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
)
_CSV_HEADER = [
    "frame", "sim_time", "real_time", "speed_kmh",
    "pos_x", "pos_y", "pos_z",
    "surge", "sway", "heave", "roll", "pitch", "yaw",
    "event", "turn_scale",
]
_csv_file = None
_csv_writer = None

def _finalize_csv():
    global _csv_file
    if _csv_file:
        try:
            _csv_file.close()
        except Exception:
            pass
    if not CSV_ENABLED or not os.path.exists(_csv_path):
        return
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "6DOF"
        with open(_csv_path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                ws.append(row)
        xlsx_path = _csv_path.replace(".csv", ".xlsx")
        wb.save(xlsx_path)
        print(f"[Excel] 저장 완료 → {xlsx_path}")
    except ImportError:
        print("[Excel] openpyxl 없음 → pip install openpyxl")
    except Exception as e:
        print(f"[Excel] 변환 실패: {e}")

if CSV_ENABLED:
    _csv_file = open(_csv_path, "w", newline="", encoding="utf-8", buffering=1)
    _csv_writer = csv.writer(_csv_file)
    _csv_writer.writerow(_CSV_HEADER)
    print(f"[CSV] 6DOF 로그 → {_csv_path}")
    atexit.register(_finalize_csv)


def _pack(safe):
    return struct.pack(
        '<B 8f i 8f',
        1,
        safe["roll"],
        safe["pitch"],
        safe["yaw"],
        safe["sway"],
        safe["surge"],
        safe["heave"],
        0.0,
        0.0,
        1,
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
    )


def _send(packet):
    global send_fail_count
    try:
        sock.sendto(packet, (UDP_IP, UDP_PORT))
    except OSError as e:
        send_fail_count += 1
        if send_fail_count == 1 or send_fail_count % 250 == 0:
            print(f"[6DOF] UDP 송신 실패 누적 {send_fail_count}건 ({e}) — {UDP_IP}:{UDP_PORT} 확인")


def reset_pipeline():
    """새 ego/시나리오 시작 전 transform·filter·리미터·회전감쇠 상태를 처음으로."""
    global _prev_limited, _turn_scale
    reset_state()
    reset_filter()
    _prev_limited = {k: 0.0 for k in _KEYS}
    _turn_scale = 1.0


def send_neutral(duration=1.0):
    """마지막으로 보낸 6축 값 → 0 으로 duration 초 동안 선형 램프다운 후 중립 패킷.

    시나리오 종료·전환·오류 때 플랫폼이 마지막 자세에 멈춰 있지 않게 한다(블로킹).
    끝나면 reset_pipeline() 으로 다음 시나리오가 0 에서 시작하게 한다.
    """
    last = dict(_prev_limited)
    steps = max(1, int(round(duration / DT))) if any(abs(v) > 1e-6 for v in last.values()) else 1
    for i in range(1, steps + 1):
        f = 1.0 - i / steps
        _send(_pack({k: last[k] * f for k in _KEYS}))
        if i < steps:
            time.sleep(DT)
    reset_pipeline()


def process_and_send_6dof(data):
    global _prev_limited, _turn_scale, _frame_count

    accel    = data["acceleration"]
    rot      = data["rotation"]
    speed_ms = data.get("speed_kmh", 0.0) / 3.6   # B 이벤트 트리거에 사용 (A 는 무시)

    # 1. transform
    motion = _call_transform(accel, rot, speed_ms)

    # 1-b. 회전 상황 감지 → 진폭 축소 (yaw rate 기반, 램프로 부드럽게 전환)
    #      회전교차로/급커브에서 6DOF 값이 과도해지는 것을 멀미 한계 내로 억제.
    yaw_rate = abs(data.get("angular_velocity", {}).get("z", 0.0))   # deg/s
    target_scale = TURN_COMFORT_SCALE if yaw_rate > TURN_YAW_RATE_THRESH else 1.0
    _turn_scale += (target_scale - _turn_scale) * _TURN_RAMP
    motion = {k: v * _turn_scale for k, v in motion.items()}

    # 2. EMA 필터 (B 에선 이벤트 분기 자동, A 는 그냥 EMA)
    smoothed = _call_apply(motion, is_event=_is_event_active())

    # 3. 각도 축 속도 한계 안전 클램프 (병진 축 패스스루)
    safe = velocity_limiter(smoothed, _prev_limited, DT)
    _prev_limited = safe

    surge = safe["surge"]
    sway  = safe["sway"]
    heave = safe["heave"]
    yaw   = safe["yaw"]

    # 4. packet 생성
    packet = _pack(safe)

    # 5. UDP 전송 (실패해도 collector 루프가 죽지 않게 카운트만)
    _send(packet)

    event = int(_is_event_active())

    # 6. CSV 기록
    if CSV_ENABLED and _csv_writer:
        pos = data.get("position", {})
        _csv_writer.writerow([
            data.get("frame", ""),
            round(data.get("sim_time", 0.0), 4),
            round(data.get("real_time", 0.0), 4),
            round(data.get("speed_kmh", 0.0), 2),
            round(pos.get("x", 0.0), 3),
            round(pos.get("y", 0.0), 3),
            round(pos.get("z", 0.0), 3),
            round(surge, 4),
            round(sway, 4),
            round(heave, 4),
            round(safe["roll"], 4),
            round(safe["pitch"], 4),
            round(yaw, 4),
            event,
            round(_turn_scale, 4),
        ])
    _frame_count += 1
    if PRINT_EVERY > 0 and _frame_count % PRINT_EVERY == 0:
        print(
            f"6DOF 전송 | event={event} turn×{_turn_scale:.2f} "
            f"speed={speed_ms*3.6:5.1f}km/h | "
            f"Surge:{surge:+6.2f} Sway:{sway:+6.2f} Heave:{heave:+6.2f} | "
            f"Roll:{safe['roll']:+5.2f} Pitch:{safe['pitch']:+5.2f} Yaw:{yaw:+6.2f}"
        )

    # 6축 값 반환 → collector 가 WS 프레임에 합쳐 모니터(ws_monitor)로도 보냄 (#6)
    return {"roll": round(safe["roll"], 3), "pitch": round(safe["pitch"], 3),
            "yaw": round(yaw, 3), "sway": round(sway, 3), "surge": round(surge, 3),
            "heave": round(heave, 3), "event": event}


# ══════════════════════════════════════════════════════════════════
# Rust 백엔드 (sixdof_rs) — 위 Python 파이프라인을 동일 결과의 Rust 로 대체.
#   SIXDOF_BACKEND=python 이거나 sixdof_rs 가 없으면 이 블록은 비활성(위 Python 동작 그대로).
#   transform→회전감쇠→filter→limiter→100Hz 보간 송신이 전부 GIL 밖 Rust 스레드에서 돈다.
#   CSV 로깅·send_neutral·reset_pipeline·콘솔 출력·env 설정은 그대로 유지한다.
# ══════════════════════════════════════════════════════════════════
try:
    from processing import rs_engine as _rs_engine
except ImportError:
    _rs_engine = None

if _rs_engine is not None and _rs_engine.ENABLED:
    OUTPUT_HZ     = float(os.environ.get("SIXDOF_HZ", "100"))     # 100Hz 업샘플 송신
    OUTPUT_INTERP = os.environ.get("SIXDOF_INTERP", "1") != "0"   # 0 이면 tick 즉시송신(폴백)
    _rs_engine.CONFIG.update(host=UDP_IP, port=UDP_PORT, hz=OUTPUT_HZ,
                             interp=OUTPUT_INTERP, dt=DT)

    def reset_pipeline():                                   # noqa: F811
        """Rust 엔진 상태 초기화 (+ 호환용 Python 상태도 0)."""
        global _prev_limited, _turn_scale
        _rs_engine.reset()
        _prev_limited = {k: 0.0 for k in _KEYS}
        _turn_scale = 1.0

    def process_and_send_6dof(data):                        # noqa: F811
        """연산·round·패킷·100Hz 송신은 Rust 가 담당. 반환 dict·CSV·콘솔은 원본과 동일."""
        global _frame_count, send_fail_count
        m = _rs_engine.get().process_motion(data)           # Rust: 6축 계산 + 100Hz UDP 송신
        surge, sway, heave, roll, pitch, yaw, ev, ts = _rs_engine.get().last
        event = int(ev)
        send_fail_count = _rs_engine.get().send_fail_count  # 상태 리포트(motion_link)용 동기
        if CSV_ENABLED and _csv_writer:
            pos = data.get("position", {})
            _csv_writer.writerow([
                data.get("frame", ""),
                round(data.get("sim_time", 0.0), 4),
                round(data.get("real_time", 0.0), 4),
                round(data.get("speed_kmh", 0.0), 2),
                round(pos.get("x", 0.0), 3),
                round(pos.get("y", 0.0), 3),
                round(pos.get("z", 0.0), 3),
                round(surge, 4), round(sway, 4), round(heave, 4),
                round(roll, 4), round(pitch, 4), round(yaw, 4),
                event, round(ts, 4),
            ])
        _frame_count += 1
        if PRINT_EVERY > 0 and _frame_count % PRINT_EVERY == 0:
            print(
                f"6DOF 전송[rs] | event={event} turn×{ts:.2f} "
                f"speed={data.get('speed_kmh', 0.0):5.1f}km/h | "
                f"Surge:{surge:+6.2f} Sway:{sway:+6.2f} Heave:{heave:+6.2f} | "
                f"Roll:{roll:+5.2f} Pitch:{pitch:+5.2f} Yaw:{yaw:+6.2f}"
            )
        return m

    def send_neutral(duration=1.0):                         # noqa: F811
        """Rust 엔진의 마지막 setpoint → 0 으로 duration 초 동안 선형 램프다운.
        보간 스레드를 먼저 멈추고 Python 소켓으로 직접 송신한다(carla_6dof_link.neutral 과 동일).
        끝나면 엔진·파이프라인 상태를 0 으로 초기화한다."""
        surge, sway, heave, roll, pitch, yaw = _rs_engine.get().last[:6]
        _rs_engine.close()                                  # 100Hz 보간 스레드 정지(다음 process 때 재시작)
        last = {"surge": surge, "sway": sway, "heave": heave,
                "roll": roll, "pitch": pitch, "yaw": yaw}
        steps = max(1, int(round(duration / DT))) if any(abs(v) > 1e-6 for v in last.values()) else 1
        for i in range(1, steps + 1):
            f = 1.0 - i / steps
            # legacy 69B(리그 기본). SIXDOF_PACKET=official 로 바꾼 경우에도 중립은 0 수렴이라 영향 적음.
            _send(_pack({k: last[k] * f for k in _KEYS}))
            if i < steps:
                time.sleep(DT)
        reset_pipeline()

    atexit.register(_rs_engine.close)
    print("[udp_sender] Rust 백엔드(sixdof_rs) 활성 — 100Hz 보간 송신. "
          "(끄려면 SIXDOF_BACKEND=python)")
