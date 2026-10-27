"""Observe the remaining live drive and verify bounded end-of-capture stopping."""
import json
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
folder = root / "validation" / ("route-end-" + time.strftime("%Y%m%d-%H%M%S"))
folder.mkdir(exist_ok=False, parents=True)
def get():
    return json.load(urllib.request.urlopen("http://127.0.0.1:8774/state", timeout=5))
def cmd(body):
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8774/control",
        json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=5).close()
samples = []
deadline = time.monotonic() + 150
cmd({"mode": "auto"})
try:
    while time.monotonic() < deadline:
        s = get()
        samples.append(s)
        if s.get("error"):
            break
        if s.get("route_end") and s["speed_kph"] < 1:
            break
        time.sleep(.5)
    final = get()
    result = {"passed": bool(final.get("route_end") and final["speed_kph"] < 1 and not final.get("error")),
        "final": final, "samples": len(samples), "max_cross_track_m": max(x.get("cross_track_m",0) for x in samples)}
    (folder / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (folder / "samples.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    with urllib.request.urlopen("http://127.0.0.1:8774/frame.jpg", timeout=5) as response:
        (folder / "route-end.jpg").write_bytes(response.read())
    print(json.dumps(result), flush=True)
    print(folder, flush=True)
finally:
    cmd({"mode": "paused"})
