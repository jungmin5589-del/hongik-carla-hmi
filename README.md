# Hongik CARLA / NuRec Passenger HMI

Private source and configuration history for the local passenger-interaction prototype.

Three independent scenes: four-lane blocked traffic, a weaving vehicle at night,
and sudden dense fog. Passengers open the Hongik AI
notification, inspect an explanation, choose an action, then receive the observed
result and an end message. Scenario explanations use scripted simulator state;
they are not YOLO or LLM perception claims.

The five-minute fog trial stays clear for ten driving seconds, then builds dense
fog over two seconds. It requests an 8m bumper-to-bumper following gap; the
actual gap follows CARLA vehicle dynamics. A distance-increase choice still
widens the gap explicitly.

## Run in the existing authorized environment

```powershell
python open_app.py
python launch_live.py --profile fog --quality high --traffic-load standard
```

The selector is at `http://127.0.0.1:8775/`; navigation at
`http://127.0.0.1:8774/navigation`. The iPhone companion is independently paired.

- `settings/runtime-lock.json`: engine, ports, performance presets and dependencies.
- `settings/scenarios.json`: scenario timing and traffic settings.
- `docs/SETUP.md`: local runtime/data prerequisites and reproduction limits.
- `course_ui/`: the versioned navigation interface and licensed browser dependencies.
- `map_context.py` / `map_context.js`: cached OSM building footprints and roads,
  with actual CARLA vehicle positions on the navigation map. Context is loaded
  once per source; the driving renderer performs no extra inference for it.
- `record_three_scenarios.py`: record each current 720p route and copy verified
  silent MP4s into the local course folder's `시나리오별 주행영상` directory.
- `test_*.py`: focused behavior and integration checks.
- `validate_*.py`: actual local-driving checks; generated results stay outside Git.

Original NVIDIA/CARLA model archives, copied proprietary SDK sources, generated
private compatibility modules, recordings, detailed performance traces, music,
voice waveforms, pairing state, certificates and private keys are excluded. The
source-only allowlist is intentional. A clone needs the separately authorized
runtime and model data; it is not a bundled simulator installer.

The requested 30 FPS cap does not establish actual 30 FPS performance. Fog uses
an approximate depth-based atmospheric composite, not a relit or physically
simulated weather capture. The supplied scene can still contain reconstruction
limitations near its image edges.

Third-party browser code retains its own notices: Three.js r180 (MIT) and
Pretendard (SIL OFL). See `course_ui/vendor/`.
Building/road map data is © OpenStreetMap contributors, available under ODbL:
https://www.openstreetmap.org/copyright. Geographic caches remain local, outside
Git. These footprints are map context, not buildings detected from the camera;
an unmapped/forest segment may have no buildings.
