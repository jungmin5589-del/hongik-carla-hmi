"""Full cockpit requires an explicit paired tablet session, not just LAN access."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import requests

from mobile_gateway import Gateway,handler
from tablet_navigation import COOKIE,cockpit_html,clean_script,safe_state
from test_mobile_gateway import sample


class Response:
    status=200
    headers={'Content-Type':'application/json'}
    def __init__(self,data=b'{}'):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return self.data


class TabletTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.data=sample()
        self.gateway=Gateway(Path(self.tmp.name),'127.0.0.1',fetcher=lambda:copy.deepcopy(self.data))
        self.gateway.poll_once()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.gateway))
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.client=requests.Session()
    def tearDown(self):
        self.client.close();self.server.shutdown();self.server.server_close()
        self.gateway.event_log.close();self.tmp.cleanup()
    def grant(self):
        r=self.client.post(self.url+'/m/api/pair',json={'code':self.gateway.pairing.pin});self.assertEqual(r.status_code,200)
        r=self.client.get(self.url+'/m/navigation',allow_redirects=False)
        self.assertEqual(r.status_code,302);self.assertEqual(r.headers['Location'],'/navigation')
        self.assertIn(COOKIE+'=',r.headers['Set-Cookie']);self.assertIn('HttpOnly',r.headers['Set-Cookie'])
    def test_unpaired_has_pair_form_but_no_world_or_control(self):
        self.assertIn('내비게이션 연결',self.client.get(self.url+'/m/navigation').text)
        self.assertEqual(self.client.get(self.url+'/api/state').status_code,404)
        self.assertEqual(self.client.post(self.url+'/control',json={'mode':'auto'}).status_code,401)
    def test_mobile_pair_alone_does_not_expose_full_state(self):
        self.client.post(self.url+'/m/api/pair',json={'code':self.gateway.pairing.pin})
        self.assertEqual(self.client.get(self.url+'/m/api/state').status_code,200)
        self.assertEqual(self.client.get(self.url+'/api/state').status_code,404)
        self.client.get(self.url+'/m/navigation',allow_redirects=False)
        response=self.client.get(self.url+'/api/state');self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['world_pose'],self.data['world_pose'])
    def test_only_current_session_and_start_pause_forward(self):
        self.grant()
        for body in ({'mode':'auto','session_id':'old'}, {'reset':True,'session_id':'s1'}, {'quality':'fullhd','session_id':'s1'}):
            self.assertEqual(self.client.post(self.url+'/control',json=body).status_code,400)
        with patch('tablet_navigation.backend',return_value=Response()) as forward:
            self.assertEqual(self.client.post(self.url+'/control',json={'mode':'paused','session_id':'s1'}).status_code,200)
            self.assertEqual(forward.call_args.kwargs['body'],{'mode':'paused','session_id':'s1'})
        self.assertEqual(self.client.post(self.url+'/control',json={'mode':'auto','session_id':'s1'},headers={'Origin':'https://evil.example'}).status_code,403)
    def test_private_files_and_path_traversal_stay_closed(self):
        self.grant()
        for path in ('/server-key.pem','/mobile-data/handset.json','/vendor/../../mobile-data/vapid.pem','/vendor/arbitrary.py','/api/anything'):
            self.assertEqual(self.client.get(self.url+path).status_code,404)
    def test_existing_native_html_and_operator_source_are_reused(self):
        html=b'<head></head><canvas id="scene"></canvas><div class="music-dock"></div>'
        output=cockpit_html(html)
        self.assertIn(b'id="scene"',output);self.assertIn(b'class="music-dock"',output)
        self.assertEqual(output.count(b'/tablet-boot.js'),1)
        output=clean_script(b"const phone=document.createElement('a');\nconst keep=1;\nlocation.assign('http://127.0.0.1:8775/')",'/nurec-nav.js')
        self.assertNotIn(b'const phone=',output);self.assertIn(b'const keep=1',output);self.assertIn(b"location.assign('/')",output)
    def test_full_state_excludes_arbitrary_backend_metadata(self):
        data=sample();data['unrelated_private']='not-for-tablet';data['nurec']['source_file']='not-for-tablet'
        result=safe_state(data)
        self.assertIn('actors',result);self.assertIn('world_pose',result)
        self.assertNotIn('not-for-tablet',json.dumps(result))
    def test_expired_tablet_cookie_requests_repair(self):
        self.grant();self.gateway.pairing.device['expires']=0
        self.assertEqual(self.client.get(self.url+'/api/state').status_code,401)
    def test_active_trial_cannot_be_replaced_from_tablet(self):
        self.grant()
        body={'profile':'fog','condition':'B','presentation':'midterm'}
        with patch('tablet_navigation.backend') as forward:
            self.assertEqual(self.client.post(self.url+'/api/select',json=body).status_code,400)
            forward.assert_not_called()

    def test_research_registration_and_language_forward_but_admin_is_private(self):
        self.grant()
        with patch('tablet_navigation.backend',return_value=Response()) as forward:
            body={'name':'P-CN-001','language':'zh'}
            self.assertEqual(self.client.post(self.url+'/api/participant',json=body).status_code,200)
            forward.assert_called_with('/api/participant',body=body)
            self.assertEqual(self.client.get(self.url+'/api/research-voice?lang=zh').status_code,200)
            forward.assert_called_with('/api/research-voice?lang=zh')
            self.assertEqual(self.client.get(self.url+'/api/research-voice?lang=invalid').status_code,200)
            forward.assert_called_with('/api/research-voice?lang=ko')
            forward.reset_mock()
            for path in ('/admin','/admin/api/trials','/admin/export?kind=events','/research.sqlite3','/drive-config.json'):
                self.assertEqual(self.client.get(self.url+path).status_code,404)
            forward.assert_not_called()
            self.assertEqual(self.client.post(self.url+'/api/participant',json={'name':'P001','directory':'not-allowed'}).status_code,400)


if __name__=='__main__':unittest.main()
