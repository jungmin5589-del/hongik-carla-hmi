import carla
import time
import os
import sys
import threading
"""
역할 : CARLA에 데이터 요청, 6dof & DB & Websocket 으로 분배.
"""

# data-server 디렉터리를 sys.path에 올려서 시나리오 프로세스에서 import 해도
# `from sender.udp_sender ...`가 동작하도록 보정
_DATA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DATA_SERVER_DIR not in sys.path:
    sys.path.insert(0, _DATA_SERVER_DIR)

from sender.udp_sender import process_and_send_6dof, reset_pipeline, send_neutral, DT
from sender.udp_sender import sock
from sender.websocket_sender import start_ws_server, publish_frame, stop_ws_server


def _viewer_frame(data, map_short, actor_id):
    """collector data → HDMap 웹 뷰어(index.html)가 받는 프레임 형식."""
    p = data["position"]
    r = data["rotation"]
    return {
        "map": map_short,
        "id": actor_id,
        "x": round(p["x"], 3),
        "y": round(p["y"], 3),
        "z": round(p["z"], 3),
        "yaw": round(r["yaw"], 2),
        "speed": round(data["speed_kmh"], 2),
        "t": round(data["real_time"], 3),
    }


def _build_data(snapshot, vehicle):
    transform = vehicle.get_transform()
    velocity = vehicle.get_velocity()
    accel = vehicle.get_acceleration()
    angular_vel = vehicle.get_angular_velocity()

    speed = (
        (velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2) ** 0.5
    ) * 3.6

    return {
        "frame": snapshot.frame,
        "sim_time": snapshot.timestamp.elapsed_seconds,
        "real_time": time.time(),
        "speed_kmh": speed,
        "position": {
            "x": transform.location.x,
            "y": transform.location.y,
            "z": transform.location.z,
        },
        "rotation": {
            "roll": transform.rotation.roll,
            "pitch": transform.rotation.pitch,
            "yaw": transform.rotation.yaw,
        },
        "velocity": {
            "x": velocity.x,
            "y": velocity.y,
            "z": velocity.z,
        },
        "acceleration": {
            "x": accel.x,
            "y": accel.y,
            "z": accel.z,
        },
        "angular_velocity": {
            "x": angular_vel.x,
            "y": angular_vel.y,
            "z": angular_vel.z,
        },
    }


# ──────────────────────────────────────────────────────────────
# 백그라운드 모드용 상태
# ──────────────────────────────────────────────────────────────
_stop_event = threading.Event()
_thread = None


def _collector_loop(world, vehicle):
    print("[Collector] 6DOF 송신 루프 시작 (background)")
    map_short = world.get_map().name.split("/")[-1]
    actor_id = vehicle.id
    next_due = None
    while not _stop_event.is_set():
        try:
            # 동기 시나리오: 메인 루프의 world.tick() / 비동기 시나리오: 서버 tick → 그 tick을 기다림
            snapshot = world.wait_for_tick(seconds=2.0)
        except RuntimeError:
            continue

        if not vehicle.is_alive:
            print("[Collector] ego 차량이 사라짐 → 루프 종료")
            break

        # 비동기(가변 tick) 월드에서도 6DOF 파이프라인이 가정하는 DT(25Hz)로 처리.
        # A 의 yaw cue 는 프레임당 heading 변화량이라 tick 수에 비례해 커지기 때문.
        # 시뮬레이션 시간 기준 예정 시각 누적 → 평균 주기가 정확히 DT.
        sim_t = snapshot.timestamp.elapsed_seconds
        if next_due is not None and sim_t < next_due - 1e-4:
            continue
        next_due = sim_t + DT if next_due is None or sim_t - next_due > DT else next_due + DT

        data = _build_data(snapshot, vehicle)
        motion = process_and_send_6dof(data)              # 6DOF UDP (+ 6축 반환)
        frame = _viewer_frame(data, map_short, actor_id)  # CARLA 위치 (HDMap 뷰어용)
        if isinstance(motion, dict):
            frame["motion"] = motion                      # 6DOF 6축·event 중첩 → ws_monitor 표시 (#6)
        publish_frame(frame)                              # 위치+6DOF 한 프레임 (yaw 충돌 없게 중첩)

    print("[Collector] 6DOF 송신 루프 종료")


def detach_collector(neutral=True):
    """백그라운드 루프만 멈춤(WS 서버·UDP 소켓 유지). 시나리오 전환/종료 때 사용.

    neutral=True 면 마지막 6축 값 → 0 으로 램프다운한 뒤 중립 패킷을 보낸다.
    """
    global _thread
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=3.0)
        _thread = None
    if neutral:
        send_neutral()


def stop_collector():
    detach_collector(neutral=True)
    stop_ws_server()
    try:
        sock.close()
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# 메인 엔트리포인트
#   - run_collector()                              → 단독 실행 (data-server/main.py)
#   - run_collector(world, vehicle, background=True) → 시나리오 내부에서 백그라운드 스레드로
# ──────────────────────────────────────────────────────────────

def run_collector(world=None, vehicle=None, background=False):
    if background:
        if world is None or vehicle is None:
            raise ValueError("background=True 모드에서는 world와 vehicle을 넘겨야 합니다.")
        global _thread
        if _thread is not None and _thread.is_alive():
            print("[Collector] 이미 실행 중")
            return
        _stop_event.clear()
        reset_pipeline()   # 새 ego → 필터·리미터 상태 0 에서 시작
        start_ws_server()  # HDMap 웹 뷰어용 인프로세스 WebSocket 서버 (ws://127.0.0.1:8765)
        _thread = threading.Thread(
            target=_collector_loop, args=(world, vehicle), daemon=True
        )
        _thread.start()
        return

    # ── 단독 실행 모드 ────────────────────────────────────────
    # 1. CARLA 연결 설정
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()

    # 2. request 주기 설정
    settings = world.get_settings()

    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.02

    world.apply_settings(settings)

    # 3. 대상 차량(ego) 설정
    vehicle = None

    for actor in world.get_actors().filter('vehicle.*'):
        if actor.attributes.get('role_name') == 'hero':
            vehicle = actor
            break

    if vehicle is None:
        print("ego_vehicle을 찾을 수 없습니다.")
        exit()

    print("데이터 추출 및 분배를 시작합니다.")

    map_short = world.get_map().name.split("/")[-1]
    actor_id = vehicle.id
    start_ws_server()  # HDMap 웹 뷰어용 인프로세스 WebSocket 서버

    # 4. 메인 루프 (1프레임마다 반복)
    try:
        while True:
            world.tick()
            snapshot = world.get_snapshot()

            data = _build_data(snapshot, vehicle)

            # 1. 6DOF 전송
            process_and_send_6dof(data)

            # 2. DB 저장 예정
            # save_to_db(data)

            # 3. WebSocket 송신 (HDMap 웹 뷰어)
            publish_frame(_viewer_frame(data, map_short, actor_id))

            if data["frame"] % 50 == 0:
                print(f"[{data['frame']}] {data['speed_kmh']:.1f} km/h")

    except KeyboardInterrupt:
        print("종료")
    finally:
        stop_ws_server()
        sock.close()
