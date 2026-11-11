"""Values reviewed against the supplied lab release; no motion-platform output."""
import json,os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEFAULTS=dict(carla_version='0.9.15',python_version='3.10',display=[5760,1080],
              runtime_version='0.9.16',runtime_python='3.12.10',
              fallback_position=[1920,0],historical_position=[1920,-1080],
              render=[1280,720],fov=72.,yaw=6.,eye=[0.,-.35,1.2],carpool_eye=[.9,-.35,1.6],pitch=-4.,fps=30,
              source='VLA-XAI-HMI-in-PiL_AutoUI26-v0.9.1: launch_viewer.py / viewer.py',
              motion_enabled=False)

def settings():
    cfg=dict(DEFAULTS)
    shared=ROOT/'settings/lab-shared.json'
    if shared.is_file():cfg.update(json.loads(shared.read_text(encoding='utf-8')))
    path=ROOT/'lab.local.json'
    if path.is_file():cfg.update(json.loads(path.read_text(encoding='utf-8')))
    if cfg['render'] not in ([960,540],[1280,720],[1920,1080]):raise ValueError('Unsupported lab render size')
    if cfg['display']!=[5760,1080]:raise ValueError('Calibrate a different display layout before use')
    if not 45<=cfg['fov']<=100 or not -30<=cfg['yaw']<=30:raise ValueError('Invalid calibrated field of view')
    if cfg.get('motion_enabled'):raise ValueError('This launcher does not control the motion platform')
    return cfg

def enabled():return os.environ.get('HONGIK_LAB_RIG')=='1'

def view_yaws(cfg):return {name:cfg['yaw']+offset for name,offset in [('left',-cfg['fov']),('center',0.),('right',cfg['fov'])]}

def sun_altitude(profile):return -8. if profile=='night' else 12. if profile=='carpool' else 40.
