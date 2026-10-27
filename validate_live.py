"""Bounded developer QA: real CARLA motion, braking, steering and neural frames."""
import json
import math
import time
import urllib.request
from pathlib import Path
import carla

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "validation" / time.strftime("%Y%m%d-%H%M%S")
OUT.mkdir(parents=True, exist_ok=False)
BASE = "http://127.0.0.1:8774"
client = carla.Client("127.0.0.1", 2016)
client.set_timeout(5)
world = client.get_world()


def state():
    with urllib.request.urlopen(BASE + "/state", timeout=5) as response:
        return json.load(response)


def command(body):
    request = urllib.request.Request(BASE + "/control", json.dumps(body).encode(),
                                    {"Content-Type": "application/json"})
    urllib.request.urlopen(request, timeout=5).close()


def capture(name):
    with urllib.request.urlopen(BASE + "/frame.jpg", timeout=5) as response:
        (OUT / (name + ".jpg")).write_bytes(response.read())


def sample(seconds, label, keys=None):
    samples = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if keys is not None:
            command({"keys": keys})
        item = state()
        item["heading_degrees"] = world.get_actor(item["ego_id"]).get_transform().rotation.yaw
        item.update(test=label, recorded_monotonic=time.monotonic())
        samples.append(item)
        time.sleep(.15)
    return samples


samples = []
deadline = time.monotonic() + 480
try:
    while True:
        first = state()
        if first["phase"] == "error":
            raise RuntimeError(first["error"])
        if first["phase"] == "live" and first["frames"] >= 5:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("Renderer did not produce five decoded live frames in time")
        time.sleep(1)
    command({"mode": "paused", "reset": True})
    samples += sample(2, "initial_paused")
    start = state()
    capture("start")
    command({"mode": "auto"})
    samples += sample(16, "automatic_driving")
    moving = state()
    capture("after-auto")
    command({"mode": "paused"})
    samples += sample(4, "braking")
    stopped = state()
    manual_start = state()
    command({"mode": "manual"})
    samples += sample(2, "manual_accelerate", {"w": True})
    samples += sample(.8, "manual_left", {"w": True, "a": True})
    samples += sample(.8, "manual_right", {"w": True, "d": True})
    command({"mode": "paused", "keys": {}})
    samples += sample(4, "manual_braking")
    capture("after-manual")
    end = state()
    manual_distance = math.dist(manual_start["carla_position"], end["carla_position"])
    left = [s["heading_degrees"] for s in samples if s["test"] == "manual_left"]
    right = [s["heading_degrees"] for s in samples if s["test"] == "manual_right"]
    distance = math.dist(start["carla_position"], moving["carla_position"])
    report = {"kind": "developer_control_and_camera_qa", "passed": False,
        "auto_physics_displacement_m": distance, "start": start, "after_auto": moving,
        "after_brake": stopped, "after_manual": end,
        "frame_count_increase": end["frames"] - start["frames"],
        "automatic_max_cross_track_m": max(s.get("cross_track_m", 0) for s in samples if s["test"] == "automatic_driving"),
        "automatic_max_speed_kph": max(s["speed_kph"] for s in samples if s["test"] == "automatic_driving"),
        "manual_physics_displacement_m": manual_distance,
        "manual_left_heading_change_degrees": left[-1] - left[0],
        "manual_right_heading_change_degrees": right[-1] - right[0],
        "sample_count": len(samples)}
    report["passed"] = (distance > 3 and end["frames"] > start["frames"] + 10
                        and stopped["speed_kph"] < 1 and report["automatic_max_cross_track_m"] < 3
                        and manual_distance > 1 and left[-1] - left[0] < -.1 and right[-1] - right[0] > .1
                        and all(s["phase"] == "live" and not s.get("error") for s in samples))
    (OUT / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "samples.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    print("Validation:", OUT, flush=True)
    if not report["passed"]:
        raise SystemExit(1)
finally:
    command({"mode": "paused", "keys": {}})
