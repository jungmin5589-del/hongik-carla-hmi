import base64
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from http.server import ThreadingHTTPServer

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from mobile_gateway import Pairing,Gateway,filtered_state,validate_subscription,handler


def sample():
    return dict(connected=True,timestamp=1,ego=dict(speed_kmh=29.7),world_pose=dict(x=12345,y=98765),actors=[{'secret':'source-geometry'}],
        route=dict(remaining_m=500,points=[[12,34]],destination=dict(name='4차로 저속 차량 체험')),
        session=dict(session_id='s1',stage='running',navigation=dict(id='s1-weaving',research_event=dict(active=True,pending=False,title='앞 차량 흐름',description='실험 상황',
            options=[dict(action='study_highbeam',label='하이빔',detail='두 번 점멸')],outcome=dict(phase='idle'),narration=dict(cached=True,url='/api/narration/audio/blockade.wav')))),
        nurec=dict(phase='live',scenario=dict(id='congestion_long',gap_m=9.4,elapsed_s=12,completed=False)))


def subscription(endpoint='https://web.push.apple.com/test'):
    pub=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    encode=lambda value:base64.urlsafe_b64encode(value).decode().rstrip('=')
    return dict(endpoint=endpoint,keys=dict(p256dh=encode(pub),auth=encode(b'x'*16)))


class PairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=[1000.];self.store=Pairing(Path(self.tmp.name),lambda:self.now[0])
    def tearDown(self):self.tmp.cleanup()
    def test_single_use_pairing_replaces_previous_phone_and_expires(self):
        code=self.store.nonce;first=self.store.pair(code,'phone1');self.assertTrue(self.store.authenticate(first))
        with self.assertRaises(ValueError):self.store.pair(code,'phone2')
        self.store.rotate();second=self.store.pair(self.store.pin,'phone2')
        self.assertFalse(self.store.authenticate(first));self.assertTrue(self.store.authenticate(second))
        self.now[0]+=86401;self.assertFalse(self.store.authenticate(second))
        self.assertNotIn(first,self.store.path.read_text())
    def test_rate_limit_and_expired_code(self):
        for _ in range(5):
            with self.assertRaises(ValueError):self.store.pair('wrong','peer')
        with self.assertRaisesRegex(ValueError,'1분'):self.store.pair(self.store.pin,'peer')
        self.now[0]+=601
        with self.assertRaises(ValueError):self.store.pair(self.store.pin,'peer')


class FilterTests(unittest.TestCase):
    def test_city_voice_and_direct_completion_are_forwarded_without_world_data(self):
        data=sample();event=data['session']['navigation']['research_event']
        event.update(direct_pending=True,direct_label='대화 완료',staged_options=True,hide_eta=True,
                     narration=dict(cached=True,url='/api/narration/audio/city_carpool.wav'))
        value=filtered_state(data)['event']
        self.assertTrue(value['direct_pending']);self.assertTrue(value['staged_options']);self.assertTrue(value['hide_eta'])
        self.assertEqual(value['direct_label'],'대화 완료');self.assertEqual(value['narration']['url'],'/m/audio/city_carpool.wav')
    def test_only_minimal_hmi_crosses_gateway(self):
        value=filtered_state(sample());encoded=json.dumps(value)
        for secret in ('world_pose','actors','source-geometry','points','12345','98765'):self.assertNotIn(secret,encoded)
        self.assertEqual(value['event']['options'][0]['action'],'study_highbeam')
        self.assertEqual(value['event']['narration']['url'],'/m/audio/blockade.wav')
    def test_core_error_disconnects_and_audio_is_whitelisted(self):
        data=sample();data['nurec']['error']='stale';data['session']['navigation']['research_event']['narration']['url']='/private/key.pem'
        value=filtered_state(data);self.assertFalse(value['connected']);self.assertIsNone(value['event']['narration']['url'])
    def test_push_provider_allowlist_prevents_local_or_arbitrary_requests(self):
        validate_subscription(subscription())
        for endpoint in ('http://web.push.apple.com/test','https://127.0.0.1:8774/control','https://web.push.apple.com.evil.example/test','https://evil.example/test','https://user@web.push.apple.com/test'):
            with self.assertRaises(ValueError):validate_subscription(subscription(endpoint))
        value=subscription();value['keys']['auth']='wrong'
        with self.assertRaises(ValueError):validate_subscription(value)


class NetworkTests(unittest.TestCase):
    def test_lan_change_keeps_trusted_ca_and_reissues_leaf_for_new_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);gateway=Gateway(folder,'192.168.1.10',fetcher=sample)
            try:
                root=(folder/'ca.pem').read_bytes();fingerprint=gateway.keys['ca_fingerprint'];vapid=gateway.keys['public_key']
                gateway.pairing.pair(gateway.pairing.pin,'phone');gateway.pairing.subscribe(subscription())
                with patch.object(gateway,'tls_context') as tls:
                    self.assertTrue(gateway.refresh_network('192.168.2.20'));tls.load_cert_chain.assert_called_once()
                self.assertEqual(root,(folder/'ca.pem').read_bytes());self.assertEqual(fingerprint,gateway.keys['ca_fingerprint'])
                self.assertEqual(vapid,gateway.keys['public_key']);self.assertIsNone(gateway.pairing.device['subscription'])
                cert=x509.load_pem_x509_certificate((folder/'server.pem').read_bytes())
                ips=[str(x) for x in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)]
                self.assertIn('192.168.2.20',ips);self.assertNotIn('192.168.1.10',ips)
                leaf=(folder/'server.pem').read_bytes();self.assertFalse(gateway.refresh_network('127.0.0.1'))
                self.assertEqual('192.168.2.20',gateway.address);self.assertEqual(leaf,(folder/'server.pem').read_bytes())
            finally:gateway.event_log.close()


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.data=sample();cls.sent=[];cls.event=threading.Event()
        def sender(sub,payload):cls.sent.append(payload);cls.event.set()
        cls.gateway=Gateway(Path(cls.tmp.name),'127.0.0.1',fetcher=lambda:copy.deepcopy(cls.data),sender=sender)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler(cls.gateway));threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.gateway.event_log.close();cls.tmp.cleanup()
    def setUp(self):
        self.gateway.pairing.device=None;self.gateway.pairing.rotate();self.gateway.poll_once();self.session=requests.Session()
        self.data.clear();self.data.update(sample())
    def tearDown(self):self.session.close()
    def pair(self):
        r=self.session.post(self.url+'/m/api/pair',json=dict(code=self.gateway.pairing.pin));self.assertEqual(r.status_code,200)
    def test_http_requires_pair_cookie_and_rejects_foreign_origin_host_and_private_files(self):
        self.assertEqual(self.session.get(self.url+'/m/api/state').status_code,401)
        r=self.session.post(self.url+'/m/api/pair',json=dict(code=self.gateway.pairing.pin),headers={'Origin':'https://evil.example'})
        self.assertEqual(r.status_code,403)
        self.pair();self.assertEqual(self.session.get(self.url+'/m/api/state').status_code,200)
        self.assertEqual(self.session.get(self.url+'/m/api/state',headers={'Host':'evil.example'}).status_code,403)
        for path in ('/vapid.pem','/server-key.pem','/m/../../mobile-data/ca-key.pem','/control','/frame.jpg'):
            self.assertEqual(self.session.get(self.url+path).status_code,404)
    def test_commands_cannot_start_drive_or_use_old_session(self):
        self.pair()
        for body in (dict(action='emergency_stop',session_id='s1',navigation_id='s1-weaving',request_id='1'),dict(action='study_highbeam',session_id='old',navigation_id='old-weaving',request_id='2')):
            self.assertEqual(self.session.post(self.url+'/m/api/command',json=body).status_code,400)
    def test_no_push_before_subscription_and_per_session_dedup(self):
        self.pair();before=len(self.sent);self.gateway.poll_once();self.assertEqual(len(self.sent),before)
        self.gateway.pairing.subscribe(subscription());self.event.clear();self.gateway.poll_once();self.assertTrue(self.event.wait(2))
        after=len(self.sent);self.gateway.poll_once();self.assertEqual(len(self.sent),after)
        self.assertEqual(self.sent[-1]['tag'],'s1:situation')
        self.assertNotIn('speed',json.dumps(self.sent[-1]))
    def test_pc_panel_allows_only_named_loopback_origins_without_phone_secrets(self):
        r=self.session.get(self.url+'/pc/state',headers={'Origin':'http://127.0.0.1:8774'})
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Access-Control-Allow-Origin'],'http://127.0.0.1:8774')
        self.assertEqual(len(r.json()['pin']),6)
        for secret in ('subscription','token_hash','public_key','endpoint'):self.assertNotIn(secret,r.json())
        r=self.session.get(self.url+'/pc/state',headers={'Origin':'https://evil.example'})
        self.assertEqual(r.status_code,403);self.assertNotIn('Access-Control-Allow-Origin',r.headers)
    def test_safari_vapid_subject_is_not_a_local_hostname(self):
        with patch('mobile_gateway.webpush') as send:
            self.gateway.push(subscription(),{'title':'test'})
            subject=send.call_args.kwargs['vapid_claims']['sub']
            self.assertTrue(subject.startswith('https://'));self.assertNotIn('localhost',subject);self.assertFalse(subject.endswith('.local'))
    def test_reconnected_storage_reopens_a_failed_event_log_handle(self):
        self.gateway.event_log.close();broken=Mock();broken.write.side_effect=PermissionError('stale removable storage handle')
        self.gateway.event_log=broken;self.gateway.log('storage_reconnected')
        row=json.loads((self.gateway.folder/'mobile-events.jsonl').read_text(encoding='utf-8').splitlines()[-1])
        self.assertEqual(row['event'],'storage_reconnected');broken.close.assert_called_once()


if __name__=='__main__':unittest.main()
