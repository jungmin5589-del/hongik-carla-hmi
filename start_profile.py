"""Use the same reviewed settings on the lab PC and a Windows laptop."""
import argparse,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def plan(profile,root=ROOT):
    if profile not in ('laptop','lab','motion'):raise ValueError('Unknown profile')
    value=json.loads((Path(root)/'settings/portable-motion.json').read_text(encoding='utf-8'))
    env={str(k):str(v) for k,v in value['environment'].items()}
    return dict(profile=profile,preview=profile=='laptop',motion=profile=='motion',environment=env)

def run(profile='laptop',check=False,root=ROOT):
    value=plan(profile,root)
    print(json.dumps(value,ensure_ascii=False,indent=2),flush=True)
    if check:return value
    for key,val in value['environment'].items():os.environ.setdefault(key,val)
    from lab_one_click import run as launch
    launch(root=root,preview=value['preview'],motion=value['motion'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=['laptop','lab','motion'],default='laptop');p.add_argument('--check',action='store_true')
    args=p.parse_args();run(args.profile,args.check)
