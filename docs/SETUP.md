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

Fog reuses `white_sedan` from the existing authorized local traffic asset bank
at `../source/traffic-assets-temporal-v2/` with its integrity/provenance manifest.
The local renderer sees it at `/data/traffic-assets-temporal-v2/white_sedan.ply`.
The model and its manifest are excluded from Git. Its ground offset follows
the original source road; source data licensing continues to apply.

For geographic navigation context, prepare each authorized source once:

```powershell
python prepare_map_context.py --profile night --provider osm-map
python prepare_map_context.py --profile congestion --provider osm-map
python prepare_map_context.py --profile fog --provider osm-map
```

These are three small one-off OSM extracts, transformed into the same local ENU
frame as the measured road, then mirrored into CARLA XY. The default Overpass
provider is also available. Raw/converted geographic data is cached in
`../cache/map-context/` and excluded from Git. Existing caches are preserved.
The navigation service reads the cache once and needs no map network access
during driving. Display © OpenStreetMap contributors and the ODbL link on the
map; data license: https://www.openstreetmap.org/copyright.

`python record_three_scenarios.py` records each baseline route to its natural
end without choosing a response, verifies MP4 decoding/duration, and copies only
the finished videos into the user's course folder. Raw JPEGs and detailed traces
stay on D. The files preserve wall-clock timing in a 30fps container by repeating
frames, without interpolation; that is not a measured 30fps rendering result.
Recordings are silent and do not capture the desktop, camera or microphone.

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
