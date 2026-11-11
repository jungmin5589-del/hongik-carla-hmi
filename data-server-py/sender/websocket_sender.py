"""인프로세스 WebSocket 텔레메트리 송·수신 + 세션 로깅.

(기존) 시나리오 프로세스(main.py → collector) 안에서 WS 서버를 띄워
HDMap 웹 뷰어(index.html)로 ego 위치/속도 프레임을 브로드캐스트한다.
→ 별도의 telemetry_server.py 프로세스를 따로 켤 필요가 없다.

2026-06-04 확장 (PM 결정 ④·⑨ — `04_design/feedback_260604_decisions.md` §3-C):
  ① 양방향화 — `_handler` 가 클라(React HMI A/B·모니터)가 보낸 메시지를 `async for` 로
     수신한다(기존엔 `wait_closed()` 만 하여 일방향이었음). → HMI 반응/입력이 서버로 돌아옴.
  ② 단일 권위 시계 `t_bus` — 서버가 중계하는 모든 메시지(발신 프레임·수신 HMI 메시지)에
     단조시계(time.monotonic) 1개를 찍는다. 장치 시계차 없이 동기·latency 가 성립.
  ③ JSONL 세션 로거 — WebSocket 이 "센서 텔레메트리 로그 ∧ 실험 트래킹 로그"의 이중 역할.
     publish_frame(센서 스트림)과 수신 HMI 상호작용을 한 파일(JSONL)에 같은 t_bus 축으로
     남긴다. → `scenarios/tools/scenarioQA.py` 가 이 로그를 읽어 시나리오 6지표를 사후 산출.

하위호환: 기존 HDMap 뷰어는 그대로 동작한다(publish_frame 브로드캐스트 유지, 프레임에
키만 몇 개 더 붙을 뿐 뷰어는 모르는 키를 무시). 양방향·로깅은 순수 추가.
브라우저는 CARLA RPC(2000)에 직접 못 붙으므로 파이썬이 ws://<host>:8765 로 중계하는 구조는 유지.
websockets 패키지가 없으면 조용히 비활성화된다(지도/시나리오는 그대로 동작).

사용:
    from sender.websocket_sender import start_ws_server, publish_frame, stop_ws_server
    start_ws_server(port=8765)              # log_path=None → 자동 파일명, False → 로깅 끔
    publish_frame({"map":"Town04","id":1,"x":..,"y":..,"z":..,"yaw":..,"speed":..,"t":..})
    stop_ws_server()
"""
import asyncio
import json
import os
import threading
import time

try:
    import websockets
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False

_loop = None
_thread = None
_clients = set()
_stop_evt = None          # asyncio.Event (이벤트 루프 스레드 소유)
_started = threading.Event()

# ── 세션 JSONL 로거 (센서 ∧ 실험 트래킹 로그) ──
_log_fh = None
_log_lock = threading.Lock()
_t0 = None                # 서버 시작 시각(monotonic) — t_bus 의 0점


def _now_bus():
    """단조 증가 권위 시계(초). 서버 시작을 0으로 둔다."""
    return (time.monotonic() - _t0) if _t0 is not None else time.monotonic()


def _open_log(log_path):
    """세션 로그 파일 열기. None→자동(ws_session_<epoch>.jsonl / $WS_LOG), False→비활성."""
    global _log_fh
    if log_path is False:
        _log_fh = None
        return
    if log_path is None:
        log_path = os.environ.get("WS_LOG") or f"ws_session_{int(time.time())}.jsonl"
    try:
        _log_fh = open(log_path, "a", encoding="utf-8")
        print(f"[WS] 세션 로그 → {os.path.abspath(log_path)} (센서 ∧ 실험 트래킹 JSONL)")
    except OSError as e:
        print(f"[WS] 세션 로그 파일 열기 실패({e}) → 로깅 비활성")
        _log_fh = None


def _log_jsonl(obj):
    """t_bus 스탬프된 메시지 1건을 JSONL 한 줄로 기록(스레드 안전)."""
    if _log_fh is None:
        return
    try:
        line = json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return
    with _log_lock:
        try:
            _log_fh.write(line + "\n")
            _log_fh.flush()
        except OSError:
            pass


def _broadcast(text):
    """연결된 모든 클라로 텍스트 1건 브로드캐스트(이벤트 루프 스레드 안전)."""
    if _loop is None or not _clients:
        return
    try:
        _loop.call_soon_threadsafe(websockets.broadcast, list(_clients), text)
    except RuntimeError:
        pass  # 루프가 닫히는 중


async def _handler(conn):
    _clients.add(conn)
    try:
        # 양방향(2026-06-04): HMI(React A/B)·모니터가 보낸 메시지를 수신해
        # t_bus 스탬프 후 세션 로그에 남기고, 모니터가 볼 수 있게 echo 한다.
        async for raw in conn:
            try:
                msg = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(msg, dict):
                msg = {"value": msg}
            msg.setdefault("type", "hmi_interaction")   # HMI 반응/입력 기본 타입
            msg.setdefault("source", "hmi")
            msg["t_bus"] = _now_bus()                    # 단일 권위 시계
            _log_jsonl(msg)                              # 실험 트래킹 로그
            _broadcast(json.dumps(msg, ensure_ascii=False))  # 모니터 타임라인 표시용
    except Exception:
        # ConnectionClosed 등은 정상 종료로 간주
        pass
    finally:
        _clients.discard(conn)


async def _serve(host, port):
    global _stop_evt
    _stop_evt = asyncio.Event()
    async with websockets.serve(_handler, host, port):
        print(f"[WS] 텔레메트리 ws://127.0.0.1:{port} (in-process, 양방향+t_bus+JSONL 로깅)")
        _started.set()
        await _stop_evt.wait()


def start_ws_server(host="0.0.0.0", port=8765, log_path=None):
    """백그라운드 스레드에서 WebSocket 서버 시작. 성공 시 True.

    log_path=None → 자동 파일명(또는 환경변수 $WS_LOG), False → 세션 로깅 끔.
    """
    global _loop, _thread, _t0
    if not _WS_AVAILABLE:
        print("[WS] websockets 미설치 → 텔레메트리/로깅 비활성 "
              "(py -3.10 -m pip install \"websockets>=12\")")
        return False
    if _thread is not None and _thread.is_alive():
        return True

    _t0 = time.monotonic()
    _open_log(log_path)
    _started.clear()
    _loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(_loop)
        try:
            _loop.run_until_complete(_serve(host, port))
        except Exception as e:
            print(f"[WS] 서버 종료/오류: {e}")
        finally:
            _loop.close()

    _thread = threading.Thread(target=_run, name="ws-telemetry", daemon=True)
    _thread.start()
    if not _started.wait(timeout=5.0):
        print("[WS] 서버 시작 확인 실패 (포트 충돌? 8765 이미 사용 중일 수 있음)")
        return False
    return True


def publish_frame(frame):
    """ego/센서 한 프레임(dict)을 연결된 모든 뷰어로 브로드캐스트 + 세션 로그 기록. 비차단.

    하위호환: 기존 HDMap 뷰어 프레임({map,id,x,y,z,yaw,speed,t})은 그대로 전달.
    추가: source/type/t_bus 스탬프 + JSONL 기록(센서 스트림). 클라가 없어도 로그는 남긴다.
    """
    if not _WS_AVAILABLE or _loop is None:
        return
    if isinstance(frame, dict):
        frame.setdefault("source", "carla")
        frame.setdefault("type", "world_frame")
        frame["t_bus"] = _now_bus()
    _log_jsonl(frame)
    if not _clients:
        return
    try:
        msg = json.dumps(frame, ensure_ascii=False)
    except (TypeError, ValueError):
        return
    try:
        _loop.call_soon_threadsafe(websockets.broadcast, list(_clients), msg)
    except RuntimeError:
        pass  # 루프가 닫히는 중


def publish_event(event_type, payload=None, source="carla"):
    """scenario_event/world_metric 등 비프레임 이벤트 발행 헬퍼(선택).

    예) publish_event('scenario_event',
                      {'name':'puddle_enter','Nsec_to_recover':3,'recommended_kmh':40})
    publish_frame 경로를 그대로 타므로 동일하게 t_bus 스탬프·브로드캐스트·로깅된다.
    """
    publish_frame({"type": event_type, "source": source, "payload": payload or {}})


def stop_ws_server():
    global _thread, _log_fh
    if _loop is not None and _stop_evt is not None:
        try:
            _loop.call_soon_threadsafe(_stop_evt.set)
        except RuntimeError:
            pass
    if _thread is not None:
        _thread.join(timeout=2.0)
        _thread = None
    if _log_fh is not None:
        with _log_lock:
            try:
                _log_fh.flush()
                _log_fh.close()
            except OSError:
                pass
        _log_fh = None
