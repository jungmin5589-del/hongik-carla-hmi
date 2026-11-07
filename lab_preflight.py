"""Read-only readiness report; never starts/moves a vehicle or motion platform."""
import importlib,json,sys,subprocess
from pathlib import Path

def main():
    from lab_settings import settings,view_yaws
    from lab_viewer import monitors,surround_rect
    cfg=settings();errors=[];notes=[]
    import carla
    version=carla.Client('127.0.0.1',2026).get_client_version()
    if not version.startswith('0.9.16'):errors.append('Use the separate 0.9.16 client, not the lab legacy client')
    for name in ('get_bone_names','get_bone_world_transforms'):
        if not hasattr(carla.Walker,name):errors.append('Missing pedestrian API: '+name)
    for name in ('native_carla','pygame','PIL','mobile_gateway','lab_capture'):importlib.import_module(name)
    from voice_bank import catalog
    try:catalog()
    except Exception as exc:errors.append('Korean narration: '+type(exc).__name__)
    from city_voice import TEXTS,audio_path
    for key in TEXTS:
        try:audio_path(key)
        except Exception as exc:errors.append(key+': '+type(exc).__name__)
    from english_voice import catalog as english
    if not all(v['cached'] for v in english().values()):errors.append('English narration cache incomplete')
    from cabin_recording import verified
    from mechanical_recording import audio
    for name,check in [('recorded cabin',verified),('mechanical sound',audio)]:
        try:check()
        except Exception as exc:errors.append(name+': '+type(exc).__name__)
    from exterior_gait import CACHE
    for p in (CACHE,CACHE.with_name('walker0001.json')):
        if not p.is_file():errors.append('Missing gait '+p.name)
    rects=monitors();rect=surround_rect(rects)
    if not rect:notes.append('Physical 5760x1080 Surround not detected on this PC')
    bundled=Path(__file__).resolve().parent.parent/'CARLA_0.9.16'
    root=bundled if (bundled/'CarlaUE4.exe').is_file() else Path(cfg.get('carla_root','C:/CARLA_0.9.16'))
    if not (root/'CarlaUE4.exe').is_file():errors.append('Configure the CARLA engine folder')
    from launch_live import memory_state
    if memory_state()<16:notes.append('Less than 16 GiB commit headroom; startup guard will wait/refuse')
    try:gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits'],text=True,timeout=5,creationflags=0x08000000).strip()
    except (OSError,subprocess.SubprocessError):gpu='Not detected; check the lab GPU manually'
    from passenger_music import library
    print(json.dumps(dict(client=version,python=sys.version.split()[0],gpu=gpu,music_tracks_available=sum(t['available'] for t in library()),monitors=rects,detected_surround=rect,camera_yaws=view_yaws(cfg),render=cfg['render'],motion_enabled=False,errors=errors,notes=notes,physical_lab_validation='pending'),ensure_ascii=True,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
