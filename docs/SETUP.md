# Existing local runtime setup

This repository versions application code, the passenger UI, scenario settings,
tests and pinned runtime references. It does not contain a self-contained CARLA
or NVIDIA environment.

The working Windows layout uses:

- CARLA: `C:/CARLA_0.9.16`
- Python: `C:/CARLA_0.9.16/diagnostics/nurec-env/Scripts/python.exe`
- This checkout: `D:/CARLA-Maps/NuRec-OneScene-20261018/live`
- External licensed assets/configuration/cache: the checkout's parent directory.
- NVIDIA runtime: the pinned image in `settings/runtime-lock.json`, launched by
  `serve-live.sh` inside the existing `Ubuntu-22.04` WSL distribution.

For another machine, obtain the required CARLA/NVIDIA software and gated data
under their own terms. Restore the local data layout and generated compatibility
files separately. The `prepare_*.py` helpers verify exact source hashes before
producing private compatibility files. Original and generated NVIDIA SDK files
are deliberately not tracked here.

`profile_sources.py` reads these verified local manifests from `../reports/`:
`scene-download.json`, `long-scene-download.json`, and
`wide-long-scene-download.json`. The native map/trajectory/track data stays inside
the licensed source archives. Local scenario reports and generated depth caches
also stay outside Git. They must be supplied by the existing authorized setup;
cloning this repository alone is insufficient to drive.

Start the scenario selector with `python open_app.py`. The existing course
`48-NuRec-Long-Congestion.bat` calls the same selector. For an explicit scene:

```powershell
python launch_live.py --profile fog --quality high --traffic-load standard
```

The Sohee voice bank and its integrity manifest are local generated resources in
`../cache/sohee-narration/`; they are not uploaded. The iPhone companion requires
its own local pairing, TLS trust and notification enrollment. Certificates,
private keys, subscriptions, pairing codes and device state must never be added
to this repository.

Keep DX12, asynchronous CARLA, and the existing memory guards. The `30` FPS value
is a requested cap, not a measured performance guarantee. Simulation behavior,
perception results, fixed-frame image reviews and actual live-drive validation
are different evidence categories.
