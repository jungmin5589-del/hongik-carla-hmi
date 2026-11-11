"""Portable lab startup. Never launches or arms an unconfigured motion platform."""
import argparse,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def run(root=ROOT,preview=False,check=False,runner=subprocess.run,motion=False):
    root=Path(root);bundle=root.parent
    if check:
        runner([sys.executable,str(root/'lab_preflight.py')],cwd=root,check=True)
        return
    engine=bundle/'CARLA_0.9.16'
    if not (engine/'.hongik-engine-ready').is_file():
        if not (bundle/'CARLA_0.9.16.zip').is_file():
            raise RuntimeError('The complete portable folder is required: live, python, cache and CARLA_0.9.16.zip.')
        print('First launch: preparing the separate portable engine. Existing lab installations are preserved.',flush=True)
        runner([sys.executable,str(root/'setup_lab.py')],cwd=root,check=True)
    else:
        runner([sys.executable,str(root/'lab_preflight.py')],cwd=root,check=True)
    args=[sys.executable,str(root/'launch_lab.py'),'--welcome']
    if preview:args.append('--preview')
    if motion:args.append('--motion')
    runner(args,cwd=root,check=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview',action='store_true');parser.add_argument('--check',action='store_true')
    parser.add_argument('--motion',action='store_true',help='enable the existing PC motion and WebSocket integration')
    args=parser.parse_args();run(preview=args.preview,check=args.check,motion=args.motion)

if __name__=='__main__':main()
