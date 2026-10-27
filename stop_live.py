"""Stop only this trial's recorded process trees and pinned named container."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
owned = root / "owned-processes.json"
if owned.is_file():
    data = json.loads(owned.read_text(encoding="utf-8-sig"))
    for kind in ("display", "bridge", "carla"):
        pid = data.get(kind)
        if not isinstance(pid, int):
            continue
        check = ("$p=Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(pid) + "';"
                 "if($p){$p.CommandLine}")
        command = subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", check],
            creationflags=0x08000000).decode(errors="replace")
        expected = {"display":"live_window.py","bridge":"scene_bridge.py","carla":r"C:\CARLA_0.9.16\CarlaUE4"}[kind]
        matches = expected.lower() in command.lower()
        if kind == "carla":
            matches = matches and "-carla-rpc-port=2016" in command
        if matches:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           creationflags=0x08000000, capture_output=True)
            print("Stopped trial", kind, pid)
subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "bash", "-lc",
    "container=nurec-live-20261019; "
    "image=$(docker inspect --format '{{.Config.Image}}' $container 2>/dev/null) || exit 0; "
    "case $image in nvcr.io/nvidia/nre/nre-ga@sha256:97f43e7130c5636ce3e80ea3184d97f56a87fdd989b05cce42230881dbdea284) "
    "docker stop --timeout 10 $container;; *) exit 1;; esac"], creationflags=0x08000000)
print("NuRec trial stop completed")
