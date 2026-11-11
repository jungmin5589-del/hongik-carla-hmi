"""Lab entry: own isolated CARLA port, original navigation, calibrated three views."""
import argparse,json,os,sys,time,urllib.request
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview',action='store_true');parser.add_argument('--check',action='store_true');parser.add_argument('--welcome',action='store_true');parser.add_argument('--carla-root',type=Path)
    parser.add_argument('--motion',action='store_true',help='use the existing data-server-py 6DOF and WebSocket link')
    args=parser.parse_args()
    from lab_settings import settings
    cfg=settings()
    if args.carla_root:cfg['carla_root']=str(args.carla_root.resolve())
    bundled=Path(__file__).resolve().parent.parent/'CARLA_0.9.16'
    root=args.carla_root or (bundled if (bundled/'CarlaUE4.exe').is_file() else Path(cfg.get('carla_root',os.environ.get('CARLA_ROOT','C:/CARLA_0.9.16'))))
    if not (root/'CarlaUE4.exe').is_file():raise RuntimeError('Set the separate CARLA folder first: python launch_lab.py --carla-root "C:/your/CARLA_0.9.16"')
    if args.motion:
        from motion_link import data_server,motion_profile,websockets_available
        if not websockets_available():raise RuntimeError('The existing websockets package is required for motion telemetry')
        motion=dict(enabled=True,data_server=str(data_server()),motion_profile=motion_profile(),websocket=True)
    else:motion=dict(enabled=False)
    import carla
    version=carla.Client('127.0.0.1',2026).get_client_version()
    if not version.startswith('0.9.16'):raise RuntimeError('Use the bundled 0.9.16 client; the lab 0.9.15 installation is left unchanged')
    from lab_viewer import monitors,surround_rect
    rects=monitors();rect=surround_rect(rects)
    print(json.dumps(dict(client=version,carla_root=str(root),monitors=rects,detected_surround=rect,render=cfg['render'],fov=cfg['fov'],yaw=cfg['yaw'],motion_enabled=args.motion,motion=motion),ensure_ascii=True,indent=2))
    if not rect and not args.preview:raise RuntimeError('Enable the existing lab 5760x1080 Surround layout, or use --preview on a laptop')
    if args.check:return
    os.environ['CARLA_ROOT']=str(root);os.environ['HONGIK_LAB_RIG']='1';os.environ['HONGIK_LAB_PREVIEW']='1' if args.preview else '0'
    os.environ['HONGIK_MOTION']='1' if args.motion else '0'
    if args.carla_root:
        local=Path(__file__).resolve().parent/'lab.local.json'
        if local.exists():
            import shutil,uuid
            shutil.copy2(local,local.with_name('lab.local.'+uuid.uuid4().hex+'.backup'))
        local.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    import launch_native_carla as launcher
    if launcher.listening(8774):
        with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=3) as response:state=json.load(response)
        if state.get('kind')!='hongik-native-carla':raise RuntimeError('Another app is using 8774; left unchanged')
        if not state.get('lab_rig') or bool((state.get('motion') or {}).get('enabled'))!=args.motion:
            launcher.stop_native()
            deadline=time.monotonic()+8.
            while (launcher.listening(8774) or launcher.listening(2026)) and time.monotonic()<deadline:time.sleep(.2)
    # Prevent this launcher's flags from being interpreted by the native launcher.
    sys.argv=[sys.argv[0]]
    launcher.main(start_path='/lab' if args.welcome else '/')

if __name__=='__main__':main()
