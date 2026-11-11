"""6DOF link with a fake asynchronous world; UDP goes to a local receiver, never port 10000."""
import json,math,os,socket,struct,tempfile,threading,time,unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

PACKET=struct.Struct('<B8fi8f')

class FakeWorld:
    """Async-style world: server ticks at 50Hz sim time regardless of clients."""
    def __init__(self):self.t=0.;self.frame=0;self.lock=threading.Lock()
    def get_map(self):return NS(name='Carla/Maps/Town04')
    def wait_for_tick(self,seconds=2.):
        time.sleep(.02)
        with self.lock:self.t+=.02;self.frame+=1;return NS(frame=self.frame,timestamp=NS(elapsed_seconds=self.t))

class FakeEgo:
    id=7;is_alive=True
    def __init__(self,world):self.world=world
    def _v(self,x=0.,y=0.,z=0.):return NS(x=x,y=y,z=z)
    def get_transform(self):
        t=self.world.t
        return NS(location=self._v(10*t,0.,0.),rotation=NS(roll=2.*math.sin(t),pitch=0.,yaw=20.*t))
    def get_velocity(self):return self._v(10.,0.,0.)
    def get_acceleration(self):return self._v(2.5,1.5,9.81)
    def get_angular_velocity(self):return self._v(0.,0.,20.)

class MotionLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rx=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);cls.rx.bind(('127.0.0.1',0));cls.rx.settimeout(.2)
        free=socket.socket();free.bind(('127.0.0.1',0));ws_port=free.getsockname()[1];free.close()
        cls.tmp=tempfile.TemporaryDirectory()
        os.environ.update(HONGIK_MOTION='1',SIXDOF_UDP_HOST='127.0.0.1',SIXDOF_UDP_PORT=str(cls.rx.getsockname()[1]),
                          SIXDOF_CSV='0',SIXDOF_PRINT_EVERY='0',HONGIK_MOTION_WS_PORT=str(ws_port),SCENARIO='B',
                          WS_LOG=os.path.join(cls.tmp.name,'ws.jsonl'))
        from motion_link import MotionLink
        cls.link=MotionLink(cls.tmp.name);cls.ws_port=ws_port
    @classmethod
    def tearDownClass(cls):
        cls.link.close();cls.rx.close();cls.tmp.cleanup()

    def drain(self,seconds):
        packets=[];end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:packets.append(self.rx.recv(256))
            except socket.timeout:pass
        return packets

    def test_follows_ego_at_25hz_then_ramps_to_neutral(self):
        self.assertEqual(self.link.status['motion_profile'],'A')  # stray SCENARIO=B is ignored
        world=FakeWorld();self.drain(.3)
        self.link.attach(world,FakeEgo(world),'congestion')
        self.assertTrue(self.link.status['attached'])
        started=world.t;packets=self.drain(2.);ticks=world.t-started
        self.assertTrue(all(len(p)==PACKET.size==69 for p in packets))
        rate=len(packets)/ticks
        expected=100 if getattr(self.link.udp,'OUTPUT_INTERP',False) else 25
        self.assertGreater(rate,expected*.75);self.assertLess(rate,expected*1.3)
        axes=[PACKET.unpack(p)[1:7] for p in packets]
        self.assertTrue(any(abs(v)>1e-3 for a in axes for v in a))
        self.link.detach();ramp=self.drain(.4)
        self.assertFalse(self.link.status['attached'])
        self.assertGreaterEqual(len(ramp),10)
        self.assertEqual(PACKET.unpack(ramp[-1])[1:7],(0.,)*6)
        self.assertEqual(self.drain(.3),[])  # nothing after neutral until the next attach

    def test_reattach_starts_from_a_reset_pipeline(self):
        outputs=[];process=self.link.collector.process_and_send_6dof
        def capture(data):
            result=process(data);outputs.append(result);return result
        with patch.object(self.link.collector,'process_and_send_6dof',side_effect=capture):
            for profile in ('fog','night'):
                world=FakeWorld();outputs.clear()
                self.link.attach(world,FakeEgo(world),profile)
                try:self.assertTrue(self.drain(.5))
                finally:self.link.detach();self.drain(.3)
                self.assertTrue(outputs)
                if profile=='fog':first=outputs[0]
                else:self.assertEqual(first,outputs[0])
        # Compare computed setpoints; Rust's timed interpolation may send a
        # different number of intermediate packets before the first sample.

    @unittest.skipUnless(__import__('motion_link').websockets_available(),'websockets not installed in this Python')
    def test_websocket_frame_carries_motion(self):
        import asyncio,websockets
        world=FakeWorld();self.link.attach(world,FakeEgo(world),'cargo')
        async def receive():
            async with websockets.connect(f'ws://127.0.0.1:{self.ws_port}') as ws:
                for _ in range(50):
                    msg=json.loads(await asyncio.wait_for(ws.recv(),2.))
                    if msg.get('type')=='world_frame':return msg
        try:frame=asyncio.run(receive())
        finally:self.link.detach();self.drain(.3)
        self.assertEqual(frame['id'],7);self.assertEqual(frame['map'],'Town04')
        self.assertEqual(set(frame['motion']),{'roll','pitch','yaw','sway','surge','heave','event'})

if __name__=='__main__':unittest.main()
