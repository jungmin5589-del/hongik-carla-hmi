"""Optional 6DOF link: data-server-py collector -> MotionHouse UDP + WebSocket telemetry.

Off unless HONGIK_MOTION=1 (set by launch_lab.py --motion / 55_LAB_START_MOTION.bat).
The motion math, UDP packet and WebSocket server stay in data-server-py; this module
finds it, attaches the current ego and ramps the platform to neutral whenever a
scenario is torn down or fails. Not a substitute for the rig's own neutral/e-stop.
"""
import os,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def enabled():return os.environ.get('HONGIK_MOTION')=='1'

def data_server():
    # Inside the copied lab bundle first, then next to it (development layout).
    for folder in (os.environ.get('HONGIK_DATA_SERVER'),ROOT.parent/'data-server-py',ROOT/'data-server-py',ROOT.parent.parent/'data-server-py'):
        if folder and (Path(folder)/'collector'/'carla_collector.py').is_file():return Path(folder).resolve()
    raise RuntimeError('data-server-py not found. Copy it into the lab bundle folder or set HONGIK_DATA_SERVER.')

def motion_profile():
    # data-server-py tuning: A (comfort / roundabout) or B (hydroplaning events).
    profile=os.environ.get('HONGIK_MOTION_PROFILE','A').strip().upper() or 'A'
    if profile not in ('A','B'):raise ValueError('HONGIK_MOTION_PROFILE must be A or B')
    return profile

def websockets_available():
    try:import websockets  # noqa: F401
    except ImportError:return False
    return True

class MotionLink:
    def __init__(self,run_dir):
        folder=data_server()
        # processing/transforms reads SCENARIO once at import; never inherit a stray shell value.
        os.environ['SCENARIO']=motion_profile()
        os.environ.setdefault('SIXDOF_PRINT_EVERY','25')
        os.environ.setdefault('WS_LOG',str(Path(run_dir)/'ws-session.jsonl'))
        if str(folder) not in sys.path:sys.path.append(str(folder))
        from collector import carla_collector
        from sender import udp_sender,websocket_sender
        self.collector,self.udp,self.ws=carla_collector,udp_sender,websocket_sender
        port=int(os.environ.get('HONGIK_MOTION_WS_PORT','8765'))
        ws=websocket_sender.start_ws_server(port=port)
        self.status=dict(enabled=True,attached=False,profile=None,data_server=str(folder),motion_profile=os.environ['SCENARIO'],
                         udp=f'{udp_sender.UDP_IP}:{udp_sender.UDP_PORT}',websocket=f'ws://127.0.0.1:{port}' if ws else None)
        print('6DOF link: '+str(self.status),flush=True)

    def attach(self,world,ego,profile):
        self.detach()
        self.collector.run_collector(world,ego,background=True)
        self.status.update(attached=True,profile=profile)
        self.ws.publish_event('scenario_event',dict(name='scenario_start',profile=profile,ego_id=ego.id,
                                                    motion_profile=self.status['motion_profile']),source='hongik_native')

    def detach(self):
        if not self.status['attached']:return
        self.collector.detach_collector(neutral=True)
        self.ws.publish_event('scenario_event',dict(name='scenario_end',profile=self.status['profile']),source='hongik_native')
        self.status.update(attached=False,send_failures=self.udp.send_fail_count)

    def close(self):
        self.detach();self.collector.stop_collector();self.status['websocket']=None
