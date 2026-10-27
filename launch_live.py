"""Start the independent local trial. Preserve the course 36 entry point."""
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
import argparse
from profile_sources import manifest_name,source_id

ROOT = Path(__file__).resolve().parent
PYTHON = Path(r"C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe")
CARLA = Path(r"C:\CARLA_0.9.16")
NO_WINDOW = 0x08000000
RENDER_BACKENDS = {'congestion': 'trained', 'night': 'trained', 'fog': 'trained'}


def open_port(port):
    with socket.socket() as sock:
        sock.settimeout(.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def can_reuse_drive(state,profile,renderer='trained',night_mode='straight'):
    return (state.get('profile','night')==profile and state.get('scene_id')==source_id(profile)
            and state.get('renderer_backend','trained')==renderer
            and (profile!='night' or state.get('night_mode')==night_mode)
            and state.get('phase')!='error' and not state.get('error'))


def memory_state():
    # Same guard as the established launcher: available system commit, not free RAM.
    class Performance(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong)] + [(n, ctypes.c_size_t) for n in (
            "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable",
            "SystemCache", "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize")] + [
            ("HandleCount", ctypes.c_ulong), ("ProcessCount", ctypes.c_ulong), ("ThreadCount", ctypes.c_ulong)]
    state = Performance()
    state.cb = ctypes.sizeof(state)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(state), state.cb):
        raise ctypes.WinError()
    return (state.CommitLimit - state.CommitTotal) * state.PageSize / 1024**3


def require_startup_memory(timeout=30.):
    """Keep the 16GiB floor; allow released allocations a bounded reclaim delay."""
    deadline=time.monotonic()+min(30.,max(0.,timeout))
    headroom=memory_state()
    if headroom<16.:print('Waiting for memory from the previous run to be released...',flush=True)
    while headroom<16. and time.monotonic()<deadline:
        time.sleep(1.);headroom=memory_state()
    print(f"CARLA commit headroom: {headroom:.1f} GiB (16 GiB required)",flush=True)
    if headroom<16.:
        raise RuntimeError('Less than 16 GiB commit headroom; close unused apps before starting CARLA')
    return headroom


def open_displays(owned):
    if '--no-ui' in sys.argv:
        return
    pid = owned.get('display')
    running = False
    if isinstance(pid, int):
        query = "$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(pid)+"';if($p){$p.CommandLine}"
        command = subprocess.check_output(['powershell.exe','-NoProfile','-Command',query],creationflags=NO_WINDOW).decode(errors='replace')
        running = 'live_window.py' in command and str(ROOT).lower() in command.lower()
    if not running:
        stamp = time.strftime('%Y%m%d-%H%M%S')
        log = (ROOT/'launches'/('display-'+stamp+'.log')).open('w',encoding='utf-8')
        env = dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='1')
        process = subprocess.Popen([str(PYTHON),str(ROOT/'live_window.py')],cwd=ROOT,
            stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW,env=env)
        owned['display'] = process.pid
        (ROOT/'owned-processes.json').write_text(json.dumps(owned,indent=2),encoding='utf-8')
    if '--no-browser' not in sys.argv:
        webbrowser.open('http://127.0.0.1:8774/navigation')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',choices=['night','congestion','fog'],default='night')
    parser.add_argument('--night-mode',choices=['straight','overtake-crash'],default='straight')
    parser.add_argument('--no-ui',action='store_true')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--renderer', choices=['trained','nrend','gsplat','gsplat-native'], default=None)
    parser.add_argument('--fps', type=float, default=30.)
    parser.add_argument('--proxy-update-mode', choices=['direct','batch'], default='batch')
    parser.add_argument('--scenario-load',choices=['full','essential'],default='essential')
    parser.add_argument('--quality',choices=['high','balanced'],default='high')
    parser.add_argument('--traffic-load',choices=['standard','compact'],default='standard')
    args=parser.parse_args()
    args.renderer = args.renderer or RENDER_BACKENDS[args.profile]
    if not ROOT.parent.is_dir() or not PYTHON.is_file():
        raise RuntimeError("Connect D drive and restore the existing NuRec environment")
    # Direct legacy entries also retain a working route back to the chooser.
    subprocess.run([str(PYTHON),str(ROOT/'open_app.py'),'--no-browser'],cwd=ROOT,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,creationflags=NO_WINDOW)
    if open_port(8774):
        with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=5) as response:
            state=json.load(response)
        if (can_reuse_drive(state,args.profile,args.renderer,args.night_mode)
                and state.get('target_fps') == args.fps
                and state.get('scenario_load','full') == args.scenario_load
                and state.get('traffic_load','standard') == args.traffic_load
                and state.get('proxy_update_mode') == args.proxy_update_mode):
            path = ROOT/'owned-processes.json'
            req=urllib.request.Request('http://127.0.0.1:8774/control',data=json.dumps({'quality':args.quality}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=5):pass
            open_displays(json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {})
            print("Live bridge already running")
            return
        # Verify the new source before stopping the working profile.
        manifest=manifest_name(args.profile)
        if json.loads((ROOT.parent/'reports'/manifest).read_text())['phase']!='download_verified':
            raise RuntimeError('Requested scene download is not verified')
        from switch_profile import stop_for_switch
        same_source=state.get('scene_id')==source_id(args.profile)
        same_renderer=state.get('renderer_backend','trained')==args.renderer
        same_workload=state.get('scenario_load','full')==args.scenario_load
        stop_for_switch(keep_renderer=same_source and same_renderer and same_workload and state.get('phase')!='error' and not state.get('error'))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    launch = ROOT / "launches" / stamp
    launch.mkdir(parents=True, exist_ok=False)
    owned = {}
    previous = ROOT / "owned-processes.json"
    if previous.is_file():
        display = json.loads(previous.read_text(encoding='utf-8-sig')).get('display')
        if isinstance(display, int):
            query = "$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(display)+"';if($p){$p.CommandLine}"
            command = subprocess.check_output(['powershell.exe','-NoProfile','-Command',query],creationflags=NO_WINDOW).decode(errors='replace')
            if 'live_window.py' in command and str(ROOT).lower() in command.lower():
                owned['display'] = display
    if open_port(2016) and previous.is_file():
        pid = json.loads(previous.read_text(encoding="utf-8-sig")).get("carla")
        if isinstance(pid, int):
            query = "$p=Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(pid) + "';if($p){$p.CommandLine}"
            carla_args = subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", query],
                creationflags=NO_WINDOW).decode(errors="replace")
            if "-carla-rpc-port=2016" in carla_args and r"C:\CARLA_0.9.16\CarlaUE4".lower() in carla_args.lower():
                owned["carla"] = pid
    if open_port(2016) and "carla" not in owned:
        raise RuntimeError("Port 2016 is occupied by an untracked session; inspect it before loading this trial")
    if not open_port(2016):
        headroom = require_startup_memory()
        existing = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CarlaUE4-Win64-Shipping.exe",
                                            "/FO", "CSV", "/NH"], creationflags=NO_WINDOW).decode(errors="replace")
        if "carlaue4-win64-shipping.exe" in existing.lower():
            raise RuntimeError("A different CARLA session is open. Close it before this separate trial")
        out = (launch / "carla-console.log").open("w")
        # NuRec replaces this world with its measured collision corridor.
        # Avoid loading the much larger default city just to discard it.
        p = subprocess.Popen([str(CARLA / "CarlaUE4.exe"), "/Game/Carla/Maps/Town02_Opt",
            "-dx12", "-windowed", "-ResX=640", "-ResY=360",
            "-RenderOffScreen", "-carla-rpc-port=2016"], cwd=CARLA,
            stdout=out, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        owned["carla"] = p.pid
        deadline = time.monotonic() + 180
        while not open_port(2016):
            if p.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("CARLA startup failed; see launch log")
            time.sleep(1)
    out = (launch / "bridge.log").open("w", encoding="utf-8")
    bridge_env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='1')
    render_size={'high':(1280,720),'balanced':(960,540)}[args.quality]
    bridge = subprocess.Popen([str(PYTHON), str(ROOT / "scene_bridge.py"), '--profile', args.profile,
                               '--physics-only', '--renderer-backend', args.renderer, '--night-mode', args.night_mode,
                               '--fps', str(args.fps), '--proxy-update-mode', args.proxy_update_mode,
                               '--scenario-load',args.scenario_load,'--traffic-load',args.traffic_load,
                               '--width',str(render_size[0]),'--height',str(render_size[1])], cwd=ROOT,
        stdout=out, stderr=subprocess.STDOUT, creationflags=NO_WINDOW, env=bridge_env)
    owned["bridge"] = bridge.pid
    # Build the small road BEFORE loading NuRec on GPU; avoid two large maps in VRAM.
    deadline = time.monotonic() + 180
    while not open_port(8774):
        if bridge.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError("Road/bridge startup failed; see bridge.log")
        time.sleep(1)
    if not open_port(46435):
        out = (launch / "renderer-launch.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "bash",
            "/mnt/d/CARLA-Maps/NuRec-OneScene-20261018/live/serve-live.sh", args.profile, args.renderer,args.scenario_load],
            stdout=out, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        owned["renderer_launcher"] = proc.pid
    (ROOT / "owned-processes.json").write_text(json.dumps(owned, indent=2), encoding="utf-8")
    open_displays(owned)
    print("Opened live viewer. First model load can take several minutes.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", exc, flush=True)
        sys.exit(1)
