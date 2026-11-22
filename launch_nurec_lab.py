"""Explicit NuRec lab option. Leaves motion output disabled."""
import argparse,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
from nurec_paths import data_root
from nurec_environment import python_path,carla_root,distro_name

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',choices=('congestion','night'),default='congestion')
    parser.add_argument('--quality',choices=('balanced','high'),default='balanced')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();root=data_root();live=root/'live'
    python=python_path(True);engine=carla_root(True);distro=distro_name(True)
    from profile_sources import source_id
    from lab_viewer import monitors,surround_rect
    cfg=dict(engine='nurec',profile=args.profile,scene=source_id(args.profile),display=[5760,1080],
        aspect='16:3',three_real_views=True,motion_enabled=False,render_per_view=[960,540] if args.quality=='balanced' else [1280,720],
        fullscreen=surround_rect(monitors()) is not None)
    print(json.dumps(cfg,ensure_ascii=False,indent=2),flush=True)
    if args.check:return
    # Engine switching is performed by the persistent selector, before reaching
    # here. Never terminate an untracked process simply because it owns a port.
    try:
        with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=2) as r:state=json.load(r)
    except OSError:state=None
    if state and state.get('kind')!='hongik-nurec':raise RuntimeError('CARLA 화면에서 주행을 마친 뒤 NuRec 선택 화면으로 전환해 주세요.')
    command=[str(python),str(live/'launch_live.py'),'--profile',args.profile,'--quality',args.quality,
        '--renderer','trained','--lab-surround','--natural-motion','--skip-hub']
    if cfg['fullscreen']:command.append('--surround-fullscreen')
    if args.no_browser:command.append('--no-browser')
    env=dict(os.environ,HONGIK_NUREC_ROOT=str(root),HONGIK_NUREC_PYTHON=str(python),
        HONGIK_NUREC_CARLA_ROOT=str(engine),HONGIK_NUREC_DISTRO=distro)
    # Reuse the existing verified responses from the separate native bundle;
    # do not copy recordings into Git or regenerate speech during a drive.
    candidate=Path(root.anchor)/'Hongik-CARLA-Lab-20261107/cache/research-voice'
    if not env.get('HONGIK_RESEARCH_VOICE_CACHE') and (candidate/'manifest.json').is_file():
        env['HONGIK_RESEARCH_VOICE_CACHE']=str(candidate)
    subprocess.run(command,cwd=live,env=env,check=True)

if __name__=='__main__':main()
