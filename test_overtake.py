"""Synthetic controller/command QA. These are not real CARLA/NuRec collisions."""
import ast
import io
import json
import tempfile
import threading
import unittest
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from navigation_adapter import NavigationAdapter
from night_overtake import NightOvertakeScenario
from scenario2 import Scenario2


class OvertakeBranch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.matrices = np.repeat(np.eye(4)[None], 201, axis=0)
        self.matrices[:, 0, 3] = np.linspace(0, 600, 201)
        self.trial = NightOvertakeScenario(self.matrices, Path(self.temp.name) / 'events.jsonl')
        self.trial.configure_crash_traffic([
            dict(id='car_a', kind='automobile', length=4.4, width=1.8, height=1.5),
            dict(id='car_b', kind='automobile', length=4.3, width=1.9, height=1.6)])
        for _ in range(32): self.trial.advance(.2, True, [15., 0.], 12.)
        self.trial.interaction('open', self.trial.session)
        transform=SimpleNamespace(location=SimpleNamespace(x=15.,y=0.,z=1.),rotation=SimpleNamespace(yaw=0.))
        self.bridge=SimpleNamespace(scenario=self.trial,lock=threading.Lock(),command={'mode':'auto'},
            ego=SimpleNamespace(id=1,get_transform=lambda:transform),track_actors=[],
            state=dict(phase='live',speed_kph=0.,mode='auto',width=960,height=540),
            scene=SimpleNamespace(route=self.matrices),
            world=SimpleNamespace(get_snapshot=lambda:SimpleNamespace(frame=1)))
        self.nav = NavigationAdapter(self.bridge)

    def tearDown(self):
        self.trial.events.close()
        self.temp.cleanup()

    def body(self, action, **event):
        return dict(session_id=self.trial.session, navigation_id=self.trial.session+'-weaving',
                    request_id=uuid.uuid4().hex, action=action, client_event=event)

    def choose(self):
        self.nav.command(self.body('study_open', options_visible=True))
        self.nav.command(self.body('study_choice', choice='study_overtake'))

    def start(self):
        self.choose()
        self.nav.command(self.body('study_overtake'))

    def primary(self):
        self.start()
        self.trial.on_collision('lead', 321.)  # synthetic sensor input only

    def reach_secondary(self):
        self.trial.acknowledge_crash_frame(self.trial.session, 'primary_impact')
        for _ in range(180):
            self.trial.advance(.1, True, [self.trial.ego_s, 3.15], 0.)
            if self.trial.crash_phase == 'secondary_impact': return
        self.fail('Secondary scripted contact did not start')

    def test_option_only_in_new_night_branch(self):
        self.assertEqual(self.nav.options()[-1]['label'], '추월 시도')
        self.assertFalse(self.nav.options()[-1]['disabled'])
        base = Scenario2(self.matrices, Path(self.temp.name)/'base.jsonl')
        try:
            other = NavigationAdapter(SimpleNamespace(scenario=base))
            self.assertNotIn('study_overtake', [o['action'] for o in other.options()])
        finally: base.events.close()

    def test_inspection_confirmation_idempotency_and_cancel(self):
        self.choose()
        self.assertFalse(self.trial.crash_active)
        self.nav.command(self.body('study_cancel'))
        with self.assertRaises(ValueError): self.nav.command(self.body('study_overtake'))
        self.choose()
        body = self.body('study_overtake')
        first = self.nav.command(body)
        self.assertEqual(first, self.nav.command(body))
        self.assertEqual(self.trial.crash_phase, 'pulling_out')
        with self.assertRaises(ValueError): self.nav.command(self.body('study_overtake'))

    def test_unprepared_or_route_end_cannot_act(self):
        self.trial.crash_roles = {}
        self.assertTrue(self.nav.options()[-1]['disabled'])
        self.nav.command(self.body('study_open', options_visible=True))
        with self.assertRaises(ValueError): self.nav.command(self.body('study_choice', choice='study_overtake'))
        self.assertFalse(self.trial.crash_active)

    def test_route_room_rechecked_at_execution(self):
        self.choose()
        self.trial.ego_s = self.trial.route.length - 20.
        with self.assertRaises(ValueError): self.nav.command(self.body('study_overtake'))
        self.assertFalse(self.trial.crash_active)

    def test_start_is_continuous_and_left_only(self):
        pose = self.trial.pose()[0]
        self.start()
        np.testing.assert_allclose(pose, self.trial.pose()[0])
        self.trial.advance(.1, True, [15., 0.], 12.)
        self.assertGreater(self.trial.steering_target(5.)[1], 0.)
        self.assertEqual(self.trial.public()['overtake']['direction'], 'left')
        self.assertEqual(len(self.trial.traffic_poses()), 3)
        with self.assertRaises(ValueError): self.trial.interaction('overtake_right', self.trial.session)

    def test_no_contact_never_becomes_verified_crash(self):
        self.start()
        for _ in range(270): self.trial.advance(.1, True, [15., 0.], 12.)
        self.assertEqual(self.trial.crash_phase, 'failed')
        self.assertFalse(self.trial.primary_verified)
        self.assertEqual(self.trial.outcome.status, 'unfulfilled')
        self.assertNotIn('충돌한 뒤', self.trial.outcome.summary)

    def test_unrelated_and_duplicate_contacts_do_not_fake_pileup(self):
        self.trial.on_collision('lead', 10.)
        self.assertEqual(len(self.trial.physical_contacts), 0)
        self.start()
        self.trial.on_collision('road', 100.)
        self.assertFalse(self.trial.primary_verified)
        self.trial.on_collision('lead', 100.)
        self.trial.on_collision('lead', 100.)
        self.assertTrue(self.trial.primary_verified)
        self.assertEqual(len(self.trial.physical_contacts), 1)

    def test_pause_and_render_barrier_preserve_sequence(self):
        self.primary()
        for _ in range(100): self.trial.advance(.1, True, [15., 3.15], 0.)
        self.assertEqual(self.trial.crash_phase, 'primary_impact')
        clock = self.trial.crash_clock
        self.trial.acknowledge_crash_frame('old-session', 'primary_impact')
        self.assertNotIn('primary_impact', self.trial.crash_seen)
        self.trial.acknowledge_crash_frame(self.trial.session, 'primary_impact')
        self.trial.advance(.1, False, [15., 3.15], 0.)
        self.assertEqual(self.trial.crash_clock, clock)
        self.assertEqual(self.trial.crash_phase, 'primary_impact')
        self.trial.advance(.1, True, [15., 3.15], 0.)
        self.assertEqual(self.trial.crash_phase, 'secondary_impact')

    def test_full_scripted_result_waits_for_views_observation_and_stop(self):
        self.primary()
        self.reach_secondary()
        for _ in range(25): self.trial.advance(.1, True, [15.,3.15], 0.)
        self.assertEqual(self.trial.crash_phase, 'secondary_impact')
        self.trial.acknowledge_crash_frame(self.trial.session, 'secondary_impact')
        self.trial.advance(.1, True, [15.,3.15], 0.)
        self.assertEqual(self.trial.crash_phase, 'aftermath')
        self.assertFalse(self.trial.action_complete)
        self.trial.acknowledge_crash_frame(self.trial.session, 'aftermath')
        self.trial.advance(.1, True, [15.,3.15], 0.)
        self.assertEqual(self.trial.outcome.status, 'collision')
        for _ in range(125): self.trial.advance(.1, True, [15.,3.15], 12.)
        self.assertEqual(self.trial.outcome.phase, 'stopping')
        self.assertFalse(self.trial.completed)
        for _ in range(12): self.trial.advance(.1, True, [15.,3.15], 0.)
        self.assertTrue(self.trial.completed)
        self.assertIn('추월 시도 중 충돌', self.trial.outcome.public()['message'])
        self.assertEqual(self.trial.completion_reason, 'action_outcome')
        state=self.nav.state()
        self.assertFalse(state['route']['arrived'])
        self.assertIn('충돌',state['session']['navigation']['research_event']['description'])

    def test_reset_removes_crash_and_old_requests(self):
        self.primary()
        old = self.body('study_overtake')
        self.trial.reset()
        self.assertEqual(self.trial.crash_phase, 'idle')
        self.assertFalse(self.trial.crash_seen)
        self.assertFalse(self.trial.primary_verified)
        with self.assertRaises(ValueError): self.nav.command(old)

    def test_render_timeout_does_not_erase_observed_physical_contact(self):
        self.primary()
        for _ in range(460):self.trial.advance(.1,True,[15.,3.15],0.)
        self.assertEqual(self.trial.outcome.status,'unfulfilled')
        self.assertIn('충돌은 감지',self.trial.outcome.summary)

    def test_bridge_contact_callback_maps_actual_proxy_not_static_world(self):
        source = Path(__file__).with_name('scene_bridge.py').read_text(encoding='utf-8-sig')
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Bridge')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'on_ego_collision')
        module = ast.Module(body=[method], type_ignores=[])
        namespace = {'math':__import__('math')}
        exec(compile(ast.fix_missing_locations(module), '<collision-callback>', 'exec'), namespace)
        bridge = SimpleNamespace(scenario=self.trial, track_actors=[('108',SimpleNamespace(id=99),None,None)])
        self.start()
        event = SimpleNamespace(other_actor=SimpleNamespace(id=123), normal_impulse=SimpleNamespace(x=3,y=4,z=0))
        namespace['on_ego_collision'](bridge,event)
        self.assertFalse(self.trial.primary_verified)
        event.other_actor.id=99
        namespace['on_ego_collision'](bridge,event)
        self.assertTrue(self.trial.primary_verified)
        self.assertEqual(self.trial.physical_contacts[0]['impulse'],5.)

    def test_event_provenance_separates_physics_and_scripted_motion(self):
        self.primary();self.reach_secondary()
        records=[json.loads(line) for line in Path(self.temp.name,'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertTrue(any(row['event']=='carla_collision_observed' for row in records))
        second=next(row for row in records if row['event']=='scripted_secondary_impact')
        self.assertFalse(second['physical_contact_verified'])
        self.assertNotEqual(self.trial.outcome.status,'achieved')

    def test_rear_never_enters_held_ego_view_volume(self):
        self.primary()
        self.reach_secondary()
        for _ in range(30): self.trial.advance(.1, True, [self.trial.ego_s, 3.15], 0.)
        rear = self.trial.traffic_poses()[self.trial.crash_roles['rear']]
        self.assertLessEqual(rear[0, 3], self.trial.ego_s - 6.)
        self.assertLess(abs(self.trial.pose()[2]), .2)
        self.assertGreaterEqual(self.trial.front_s-self.trial.lead_s, 4.)

    def test_configured_assets_cannot_silently_use_an_unrelated_native_car(self):
        self.trial.crash_asset_specs = [{'id':'car_a'}, {'id':'car_b'}]
        self.trial.configure_crash_traffic([
            dict(id='car_a', kind='automobile', length=4.4, width=1.8, height=1.5),
            dict(id='unrelated', kind='automobile', length=4.3, width=1.9, height=1.6)])
        self.assertFalse(self.trial.public()['overtake']['available'])

    def gateway(self):
        # Run the exact existing gateway forwarding method with an in-memory transport.
        source=Path(__file__).with_name('mobile_gateway.py').read_text(encoding='utf-8-sig')
        tree=ast.parse(source)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Gateway')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='command')
        def transport(request,timeout=None):
            try:
                if isinstance(request,str):
                    from urllib.parse import parse_qs,urlparse
                    query=parse_qs(urlparse(request).query)
                    value=self.nav.reply(query['session'][0],query['id'][0])
                else:
                    self.assertEqual(request.full_url,'http://127.0.0.1:8774/api/command')
                    value=self.nav.command(json.loads(request.data))
                return io.BytesIO(json.dumps(value).encode())
            except ValueError as error:
                raise urllib.error.HTTPError('http://127.0.0.1:8774/api/command',400,str(error),{},
                    io.BytesIO(json.dumps({'error':str(error)}).encode()))
        fake_urllib=SimpleNamespace(request=SimpleNamespace(Request=urllib.request.Request,urlopen=transport),error=urllib.error)
        scope=dict(json=json,urllib=fake_urllib,OBSERVATIONS={'study_presented','study_open','study_close','study_options','study_choice','study_cancel'})
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'<gateway>','exec'),scope)
        gateway=SimpleNamespace(state=lambda:dict(connected=True,session=self.trial.session,
            navigation_id=self.trial.session+'-weaving',event=dict(options=self.nav.options())),
            pairing=SimpleNamespace(device={'id':'synthetic-phone'}),log=lambda *args,**kw:None)
        return lambda body:scope['command'](gateway,body)

    def test_phone_gateway_executes_same_session_bound_branch(self):
        send=self.gateway()
        send(self.body('study_open',options_visible=True))
        send(self.body('study_choice',choice='study_overtake'))
        self.assertFalse(self.trial.crash_active)
        self.assertTrue(send(self.body('study_overtake'))['accepted'])
        self.assertTrue(self.trial.crash_active)

    def test_phone_gateway_rejects_close_stale_and_unapproved_controls(self):
        send=self.gateway()
        send(self.body('study_open',options_visible=True))
        send(self.body('study_choice',choice='study_overtake'))
        send(self.body('study_close'))
        with self.assertRaises(ValueError):send(self.body('study_overtake'))
        old=self.body('study_overtake');self.trial.reset()
        with self.assertRaises(ValueError):send(old)
        with self.assertRaises(ValueError):send(self.body('manual_steering'))


class BridgeCollisionHold(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name('scene_bridge.py').read_text(encoding='utf-8-sig')
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Bridge')
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('settle_after_verified_contact', 'release_collision_hold')]
        self.scope = {'carla': SimpleNamespace(Vector3D=lambda: 'zero',
                      VehicleControl=lambda **kw: kw)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])),
                     '<actual-bridge-hold>', 'exec'), self.scope)
        self.calls, self.events = [], []
        actor = SimpleNamespace(**{name: (lambda value, name=name: self.calls.append((name, value)))
            for name in ('set_target_velocity', 'set_target_angular_velocity', 'apply_control',
                         'set_simulate_physics', 'set_transform')})
        self.bridge = SimpleNamespace(ego=actor, crash_held=False, pre_contact_transform='last-safe',
            initial_transform='initial', state={}, scenario=SimpleNamespace(OVERTAKE_TRIAL=True,
                primary_verified=False, log=lambda *args, **kw: self.events.append((args, kw))))

    def test_contact_required_and_hold_applied_once(self):
        hold = self.scope['settle_after_verified_contact']
        self.assertFalse(hold(self.bridge, 'current'))
        self.assertFalse(self.calls)
        self.bridge.scenario.primary_verified = True
        self.assertTrue(hold(self.bridge, 'current'))
        self.assertTrue(self.bridge.crash_held)
        self.assertEqual(self.calls[-2:], [('set_simulate_physics', False), ('set_transform', 'last-safe')])
        self.assertTrue(self.events[0][1]['physical_contact_verified'])
        count = len(self.calls)
        hold(self.bridge, 'later')
        self.assertEqual(len(self.calls), count)

    def test_reset_restores_physics_at_initial_pose(self):
        self.bridge.crash_held = True
        self.scope['release_collision_hold'](self.bridge)
        self.assertEqual(self.calls, [('set_transform', 'initial'), ('set_simulate_physics', True)])
        self.assertFalse(self.bridge.crash_held)
        self.assertIsNone(self.bridge.pre_contact_transform)
        self.assertFalse(self.bridge.state['post_collision_hold'])

    def test_other_profiles_are_never_held(self):
        self.bridge.scenario = SimpleNamespace()
        self.assertFalse(self.scope['settle_after_verified_contact'](self.bridge, 'current'))
        self.assertFalse(self.calls)


if __name__=='__main__': unittest.main(verbosity=2)
