"""Read-only local report. Never sends vehicle/motion controls or pairing secrets."""
import argparse,datetime,json,socket,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def fetch(port,path):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=3) as r:return json.load(r)
    except (OSError,ValueError):return None
def listening(port):
    with socket.socket() as s:s.settimeout(.3);return s.connect_ex(('127.0.0.1',port))==0
def report():
    raw=fetch(8774,'/state') or {};nav=fetch(8774,'/api/state') or {};phone=fetch(8776,'/health') or {}
    value=dict(scope='Read-only local connection snapshot; no motion commands or pairing codes',
               ports={str(p):listening(p) for p in (2000,2026,8766,8774,8776,8777)},
               app={k:raw.get(k) for k in ('kind','phase','profile','error','lab_rig','departure_alignment','lane_error_m','rig')},
               navigation=dict(connected=nav.get('connected'),map=nav.get('map'),ego_id=nav.get('ego',{}).get('id'),world_pose=nav.get('world_pose')),
               tablet=dict(gateway_ready=phone.get('kind')=='hongik-mobile',polling=phone.get('polling'),address=phone.get('address'),
                           pc_setup='http://127.0.0.1:8776/connect',source='http://127.0.0.1:8774/api/state',
                           device_url=f"http://{phone['address']}:8776/m/navigation" if phone.get('address') else None),warnings=[])
    if not phone:value['warnings'].append('Mobile gateway unavailable. Run the integrated launcher or open_mobile.py on this PC.')
    if not nav.get('connected'):value['warnings'].append('Navigation source is not live. A WebSocket connection alone does not supply this HMI API.')
    if value['ports']['2026']:
        try:
            import carla
            client=carla.Client('127.0.0.1',2026);client.set_timeout(5)
            world=client.get_world();ego_id=nav.get('ego',{}).get('id');actor=world.get_actor(ego_id) if ego_id is not None else None
            engine=dict(version=client.get_server_version(),map=world.get_map().name,ego_found=actor is not None)
            if actor and nav.get('world_pose'):
                p=actor.get_location();q=nav['world_pose'];engine['navigation_position_error_m']=((p.x-q['x'])**2+(p.y-q['y'])**2)**.5
            value['engine_2026']=engine
            if ego_id is not None and not actor:value['warnings'].append('Navigation ego does not exist in engine 2026. Check the WebSocket/CARLA source mapping.')
        except (RuntimeError,OSError,ImportError) as exc:value['warnings'].append('Engine read failed: '+type(exc).__name__)
    value['warnings'].append('Actual iPad reachability, guest-Wi-Fi isolation and physical three-screen alignment require on-site checks.')
    return value
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    folder=ROOT.parent/'lab-reports';folder.mkdir(exist_ok=True)
    path=args.output or folder/('connection-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
    if path.exists():raise RuntimeError('Existing report left unchanged')
    value=report();path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(value,ensure_ascii=True,indent=2));print('Saved:',path)
if __name__=='__main__':main()
