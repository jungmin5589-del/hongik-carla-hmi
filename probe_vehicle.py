"""One-shot diagnosis of actual CARLA suspension on the source road mesh."""
import carla
import json
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8774"
def cmd(body):
    urllib.request.urlopen(urllib.request.Request(BASE + "/control", json.dumps(body).encode(),
                            {"Content-Type": "application/json"}), timeout=5).close()

c = carla.Client("127.0.0.1", 2016)
c.set_timeout(5)
w = c.get_world()
e = next(a for a in w.get_actors() if a.attributes.get("role_name","").startswith("nurec_live_ego"))
collision = w.spawn_actor(w.get_blueprint_library().find("sensor.other.collision"),
                          carla.Transform(), attach_to=e)
collisions = []
collision.listen(lambda hit: collisions.append({"other": hit.other_actor.type_id,
    "id": hit.other_actor.id, "impulse": str(hit.normal_impulse)}))
report = {"original_control": str(e.get_control()), "observations": []}
try:
    cmd({"mode": "paused"})
    e.set_simulate_physics(True)
    wp = w.get_map().get_waypoint(e.get_location())
    report["waypoint"] = {"s": wp.s, "id": wp.road_id, "lane": wp.lane_id, "transform": str(wp.transform)}
    tr = wp.transform
    tr.location.z += 1.1
    e.set_target_velocity(carla.Vector3D())
    e.set_transform(tr)
    time.sleep(1)
    cmd({"mode": "auto"})
    for _ in range(30):
        report["observations"].append({"location": str(e.get_location()), "velocity": str(e.get_velocity()),
                                        "control": str(e.get_control())})
        time.sleep(.2)
finally:
    cmd({"mode": "paused"})
    collision.stop()
    collision.destroy()
    report["collisions"] = collisions
    out = Path(__file__).with_name("vehicle-physics-probe.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
