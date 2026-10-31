"""Paired LAN handset companion; simulator/control port remains loopback-only.

Only a filtered HMI state, approved research choices, and cached Sohee audio
cross this gateway. No NuRec frames, world coordinates, source files, or driving
start/steering controls are exposed. OS push is opt-in and requires secure PWA.
"""
import base64
import hashlib
import html
import http.cookies
import ipaddress
import io
import json
import secrets
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import qrcode
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec,rsa
from cryptography.x509.oid import NameOID
from pywebpush import webpush,WebPushException

ROOT=Path(__file__).resolve().parent
DATA=ROOT.parent/'mobile-data'
ASSETS=ROOT/'mobile'
HTTP_PORT,HTTPS_PORT=8776,8777
COOKIE='hongik_mobile'
OBSERVATIONS={'study_presented','study_open','study_close','study_options','study_choice','study_cancel'}
AUDIO_NAMES={'blockade','congestion','night','fog','normal','complete','yield','city_yield','city_carpool','city_rattle'}
# Reserved example URI for this local prototype; never transmit the user's email.
# A public deployment should configure its own operator contact URI.
VAPID_SUBJECT='https://example.com'
PC_ORIGINS={f'http://{host}:{port}' for host in ('127.0.0.1','localhost') for port in (8774,8775,8776)}


def local_ip():
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
        try:probe.connect(('8.8.8.8',80));value=probe.getsockname()[0]
        except OSError:value='127.0.0.1'
    return value if ipaddress.ip_address(value).is_private else '127.0.0.1'


def b64(value):return base64.urlsafe_b64encode(value).decode().rstrip('=')


def prepare_keys(folder,address):
    """Generate local keys only. Never install a CA or change OS trust settings."""
    folder.mkdir(parents=True,exist_ok=True)
    def save_key(path,key):path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    ca_key=folder/'ca-key.pem';ca_cert=folder/'ca.pem';now=datetime.now(timezone.utc)
    if not ca_key.exists():
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048);save_key(ca_key,key)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Hongik AI local research CA')])
        cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=False,key_cert_sign=True,key_agreement=False,content_commitment=False,data_encipherment=False,crl_sign=True,encipher_only=None,decipher_only=None),critical=True).sign(key,hashes.SHA256())
        ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key=serialization.load_pem_private_key(ca_key.read_bytes(),password=None);cert=x509.load_pem_x509_certificate(ca_cert.read_bytes())
    (folder/'ca.cer').write_bytes(cert.public_bytes(serialization.Encoding.DER))
    leaf=folder/'server.pem';leaf_key=folder/'server-key.pem';meta=folder/'certificate-host.json'
    if not leaf.exists() or not meta.exists() or json.loads(meta.read_text()).get('ip')!=address or x509.load_pem_x509_certificate(leaf.read_bytes()).not_valid_after_utc<now+timedelta(days=2):
        server_key=rsa.generate_private_key(public_exponent=65537,key_size=2048);save_key(leaf_key,server_key)
        leaf_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Hongik AI handset companion')])
        names=[x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1')),x509.IPAddress(ipaddress.ip_address(address))]
        server_cert=x509.CertificateBuilder().subject_name(leaf_name).issuer_name(cert.subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=90)).add_extension(x509.SubjectAlternativeName(names),critical=False).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(key,hashes.SHA256())
        leaf.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM));meta.write_text(json.dumps(dict(ip=address)))
    vapid=folder/'vapid.pem'
    if not vapid.exists():save_key(vapid,ec.generate_private_key(ec.SECP256R1()))
    public=serialization.load_pem_private_key(vapid.read_bytes(),password=None).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    return dict(public_key=b64(public),ca_fingerprint=cert.fingerprint(hashes.SHA256()).hex())


class Pairing:
    def __init__(self,folder,clock=time.time):
        self.folder=folder;folder.mkdir(parents=True,exist_ok=True);self.clock=clock;self.lock=threading.RLock()
        self.path=folder/'handset.json';self.device=json.loads(self.path.read_text()) if self.path.exists() else None
        self.failures={};self.nonce='';self.pin='';self.expires=0;self.rotate()

    def save(self):
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.device),encoding='utf-8');temp.replace(self.path)

    def rotate(self):
        with self.lock:self.nonce=secrets.token_urlsafe(24);self.pin=f'{secrets.randbelow(1000000):06d}';self.expires=self.clock()+600

    def pair(self,value,peer):
        with self.lock:
            now=self.clock();recent=[t for t in self.failures.get(peer,[]) if t>now-60]
            if len(recent)>=5:raise ValueError('연결 코드를 여러 번 확인했어요. 1분 뒤 다시 시도해 주세요.')
            if now>self.expires or not self.nonce or not (secrets.compare_digest(value,self.nonce) or secrets.compare_digest(value,self.pin)):
                self.failures[peer]=recent+[now];raise ValueError('연결 코드가 다르거나 만료됐어요. PC의 휴대폰 연결 화면을 확인해 주세요.')
            token=secrets.token_urlsafe(32)
            self.device=dict(id=secrets.token_hex(8),token_hash=hashlib.sha256(token.encode()).hexdigest(),expires=now+86400,subscription=None,notified=[],paired_at=now)
            self.nonce='';self.expires=0;self.save();return token

    def authenticate(self,token):
        with self.lock:
            return bool(self.device and self.device['expires']>self.clock() and secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(),self.device['token_hash']))

    def subscribe(self,subscription):
        validate_subscription(subscription)
        with self.lock:self.device['subscription']=subscription;self.save()

    def mark_notification(self,key):
        with self.lock:
            d=self.device
            if not d or not d.get('subscription') or key in d['notified']:return False
            d['notified']=(d['notified']+[key])[-30:];self.save();return True


def validate_subscription(value):
    if not isinstance(value,dict):raise ValueError('알림 구독을 다시 확인해 주세요.')
    url=urlparse(value.get('endpoint',''));host=url.hostname or ''
    allowed=host in {'fcm.googleapis.com','updates.push.services.mozilla.com'} or host.endswith('.push.apple.com') or host.endswith('.notify.windows.com')
    if url.scheme!='https' or not allowed or url.username or url.password or url.port not in (None,443) or url.fragment:raise ValueError('지원하는 알림 제공자 주소가 아닙니다.')
    keys=value.get('keys',{})
    try:
        pub=base64.urlsafe_b64decode(keys['p256dh']+'===');auth=base64.urlsafe_b64decode(keys['auth']+'===')
        if len(pub)!=65 or pub[0]!=4 or len(auth)!=16:raise ValueError()
    except (KeyError,TypeError,ValueError):raise ValueError('알림 등록 키를 다시 확인해 주세요.')


def filtered_state(data):
    nav=data.get('session',{}).get('navigation',{});event=nav.get('research_event',{});raw=data.get('nurec',{});sc=raw.get('scenario',{});route=data.get('route',{})
    voice=event.get('narration',{});audio=voice.get('url') or ''
    allowed=AUDIO_NAMES
    name=audio.rsplit('/',1)[-1].removesuffix('.wav')
    narration=dict(cached=bool(voice.get('cached') and name in allowed),url='/m/audio/'+name+'.wav' if name in allowed else None)
    return dict(connected=bool(data.get('connected')) and not raw.get('error'),session=data.get('session',{}).get('session_id'),navigation_id=nav.get('id'),
        stage=data.get('session',{}).get('stage','ready'),scenario=sc.get('id'),speed_kph=data.get('ego',{}).get('speed_kmh',0),gap_m=sc.get('gap_m'),
        elapsed_s=sc.get('elapsed_s',0),remaining_m=route.get('remaining_m'),destination=route.get('destination',{}).get('name','주행'),
        high_beam_on=sc.get('high_beam',{}).get('on',False),completed=sc.get('completed',False),
        event=dict(active=bool(event.get('active')),pending=bool(event.get('pending')),title=event.get('title','주행을 기다리고 있어요'),
                   description=event.get('description',''),feedback=event.get('feedback',''),live_detail=event.get('live_detail',''),
                   options=event.get('options',[]),outcome=event.get('outcome',{}),narration=narration,
                   direct_pending=bool(event.get('direct_pending')),direct_label=event.get('direct_label','대응 완료'),
                   staged_options=bool(event.get('staged_options')),hide_eta=bool(event.get('hide_eta'))))


class NoRedirectSession(requests.Session):
    def request(self,*args,**kwargs):kwargs['allow_redirects']=False;return super().request(*args,**kwargs)


class Gateway:
    def __init__(self,folder=DATA,address=None,fetcher=None,sender=None):
        self.folder=folder;self.address=address or local_ip();self.keys=prepare_keys(folder,self.address);self.pairing=Pairing(folder)
        self.lock=threading.RLock();self.snapshot=dict(connected=False,session=None,event={});self.updated=0.;self.stop=threading.Event()
        self.fetcher=fetcher or self.fetch;self.sender=sender or self.push;self.push_error=None;self.push_sent=0
        self.last_network_refresh=0.;self.tls_context=None;self.worker_alive=False;self.log_lock=threading.RLock()
        self.event_log=(folder/'mobile-events.jsonl').open('a',encoding='utf-8',buffering=1)

    def log(self,event,**values):
        row=json.dumps(dict(event=event,utc=datetime.now(timezone.utc).isoformat(),**values),ensure_ascii=False)+'\n'
        with self.log_lock:
            try:self.event_log.write(row)
            except (OSError,ValueError):
                # Removable storage may invalidate an open handle after reconnection.
                try:self.event_log.close()
                except OSError:pass
                self.event_log=(self.folder/'mobile-events.jsonl').open('a',encoding='utf-8',buffering=1)
                self.event_log.write(row)

    def fetch(self):
        with urllib.request.urlopen('http://127.0.0.1:8774/api/state',timeout=2) as r:return json.load(r)

    def state(self):
        with self.lock:result=dict(self.snapshot)
        if time.monotonic()-self.updated>3:result['connected']=False
        device=self.pairing.device
        return dict(result,push_enabled=bool(device and device.get('subscription')),push_error=self.push_error,public_key=self.keys['public_key'])

    def poll_once(self):
        try:value=filtered_state(self.fetcher())
        except (OSError,ValueError,KeyError):value=dict(connected=False,session=None,event={})
        with self.lock:self.snapshot=value;self.updated=time.monotonic()
        if not value.get('connected') or not value.get('session'):return
        session=value['session'];events=[]
        if value['stage']=='running' and 0<value['elapsed_s']<5:events.append(('start','주행을 시작했어요','휴대폰에서 주행 상황과 선택 결과를 확인할 수 있어요.'))
        if value['event'].get('active'):events.append(('situation','새로운 주행 상황이 있어요','홍익 AI를 열어 상황 설명과 대응 방법을 확인해 보세요.'))
        if value['event'].get('outcome',{}).get('phase')=='complete':events.append(('end','요청한 대응을 마쳤어요','선택한 행동의 결과를 확인해 주세요.'))
        for kind,title,body in events:
            key=session+':'+kind
            if self.pairing.mark_notification(key):
                payload=dict(title=title,body=body,tag=key,session=session,url='/m/?event='+key)
                threading.Thread(target=self.deliver,args=(payload,),daemon=True).start()

    def refresh_network(self,address=None):
        """Reissue only the leaf certificate after a LAN change; keep the trusted CA."""
        address=address or local_ip()
        try:ip=ipaddress.ip_address(address)
        except ValueError:return False
        # A transient disconnection must not replace a working LAN identity with localhost.
        if not ip.is_private or ip.is_loopback or address==self.address:return False
        with self.lock:
            keys=prepare_keys(self.folder,address)
            if self.tls_context:self.tls_context.load_cert_chain(self.folder/'server.pem',self.folder/'server-key.pem')
            self.address=address;self.keys=keys
        # Web Push permissions and subscriptions belong to the previous IP origin.
        with self.pairing.lock:
            if self.pairing.device:
                self.pairing.device['subscription']=None;self.pairing.save()
            self.pairing.rotate()
        self.push_error=None;self.log('network_changed_repair_required')
        return True

    def loop(self):
        self.worker_alive=True
        try:
            while not self.stop.is_set():
                if time.monotonic()-self.last_network_refresh>=5:
                    self.last_network_refresh=time.monotonic()
                    try:self.refresh_network()
                    except (OSError,ValueError):self.log('network_refresh_failed')
                self.poll_once();self.stop.wait(.5)
        finally:self.worker_alive=False

    def push(self,subscription,payload):
        return webpush(subscription_info=subscription,data=json.dumps(payload,ensure_ascii=False),vapid_private_key=str(self.folder/'vapid.pem'),
            vapid_claims={'sub':VAPID_SUBJECT},timeout=8,ttl=90,headers={'Urgency':'high'},requests_session=NoRedirectSession())

    def deliver(self,payload):
        subscription=self.pairing.device.get('subscription') if self.pairing.device else None
        if not subscription:return
        try:
            self.sender(subscription,payload);self.push_error=None;self.push_sent+=1;self.log('push_provider_accepted',key=payload['tag'])
        except Exception as error:
            # Never log provider URLs, browser keys, cookies or capability tokens.
            self.push_error='시스템 알림 전송을 확인하지 못했어요. 앱을 열어 상황을 확인해 주세요.'
            status=None;reason=None
            if isinstance(error,WebPushException) and error.response is not None:
                status=error.response.status_code
                try:
                    candidate=error.response.json().get('reason','')
                    if isinstance(candidate,str) and candidate.isascii() and candidate.replace('_','').isalnum() and len(candidate)<64:reason=candidate
                except (ValueError,AttributeError):pass
            self.log('push_failed',kind=type(error).__name__,key=payload['tag'],status=status,reason=reason)
            if isinstance(error,WebPushException) and error.response is not None and error.response.status_code in (404,410):
                with self.pairing.lock:self.pairing.device['subscription']=None;self.pairing.save()

    def command(self,body):
        state=self.state();event=state.get('event',{})
        if not state.get('connected'):raise ValueError('PC와 연결이 끊겼어요. 다시 연결된 뒤 선택해 주세요.')
        if body.get('session_id')!=state.get('session') or body.get('navigation_id')!=state.get('navigation_id'):raise ValueError('이전 주행 알림이에요. 현재 상황을 다시 열어 주세요.')
        allowed=OBSERVATIONS|{o['action'] for o in event.get('options',[])}
        if event.get('direct_pending'):allowed.add('study_direct_done')
        if body.get('action') not in allowed:raise ValueError('휴대폰에서 사용할 수 없는 조작입니다.')
        request_id=body.get('request_id')
        if not isinstance(request_id,str) or not 1<=len(request_id)<=128:raise ValueError('요청을 다시 확인해 주세요.')
        details=body.get('client_event') or {}
        if not isinstance(details,dict):raise ValueError('요청 형식을 다시 확인해 주세요.')
        details={k:details[k] for k in ('choice','options_visible','client_ms','phase','event_visible') if k in details}
        details['source']='hongik_mobile';details['device']=self.pairing.device['id']
        clean=dict(action=body['action'],session_id=body['session_id'],navigation_id=body['navigation_id'],request_id=request_id,client_event=details)
        req=urllib.request.Request('http://127.0.0.1:8774/api/command',data=json.dumps(clean).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=5) as r:queued=json.load(r)
        except urllib.error.HTTPError as error:
            try:message=json.loads(error.read()).get('error')
            except ValueError:message=None
            raise ValueError(message or 'PC가 요청을 반영하지 못했어요.')
        from urllib.parse import urlencode
        url='http://127.0.0.1:8774/api/reply?'+urlencode(dict(session=body['session_id'],id=queued['command_id']))
        with urllib.request.urlopen(url,timeout=5) as r:reply=json.load(r)
        if not reply.get('accepted'):raise ValueError(reply.get('message','요청을 확인하지 못했어요.'))
        self.log('mobile_command_accepted',action=body['action'],session=state['session'])
        return reply


def handler(gateway):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def loopback(self):return ipaddress.ip_address(self.client_address[0]).is_loopback
        def secure(self):return isinstance(self.connection,ssl.SSLSocket)
        def authorized(self):
            try:cookie=http.cookies.SimpleCookie(self.headers.get('Cookie',''));value=cookie[COOKIE].value
            except (KeyError,http.cookies.CookieError):return False
            return gateway.pairing.authenticate(value)
        def check_host(self):
            host=self.headers.get('Host','').split(':')[0]
            return ipaddress.ip_address(self.client_address[0]).is_private and host in {'127.0.0.1','localhost',gateway.address}
        def send(self,value,kind='application/json; charset=utf-8',status=200,cookie=None):
            if not isinstance(value,bytes):value=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(value)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Frame-Options','DENY')
            origin=self.headers.get('Origin')
            if urlparse(self.path).path=='/pc/state' and origin in PC_ORIGINS:
                self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
            if cookie:self.send_header('Set-Cookie',cookie)
            self.end_headers();self.wfile.write(value)
        def fail(self,message,status=400):self.send(dict(error=message),status=status)
        def do_GET(self):
            if not self.check_host():self.fail('접속 주소를 확인해 주세요.',403);return
            path=urlparse(self.path).path
            if path=='/health':self.send(dict(kind='hongik-mobile',tls_port=HTTPS_PORT,address=gateway.address,polling=gateway.worker_alive));return
            if path.startswith('/pc/'):
                if not self.loopback():self.fail('PC에서만 열 수 있는 화면입니다.',403);return
                if path=='/pc/state':
                    if self.headers.get('Origin') not in (None,*PC_ORIGINS):self.fail('PC 내비에서 다시 열어 주세요.',403);return
                    if time.time()>gateway.pairing.expires:gateway.pairing.rotate()
                    device=gateway.pairing.device;valid=bool(device and device['expires']>time.time())
                    self.send(dict(address=gateway.address,pin=gateway.pairing.pin,expires=gateway.pairing.expires,paired=valid,
                                   push_enabled=bool(valid and device.get('subscription')),push_error=gateway.push_error));return
                files={'/pc/phone-link.js':('phone-link.js','application/javascript'),'/pc/phone-link.css':('phone-link.css','text/css')}
                if path in files:
                    name,kind=files[path];self.send((ROOT/'pc'/name).read_bytes(),kind+'; charset=utf-8');return
                self.send_error(404);return
            if path=='/ca.cer':self.send((gateway.folder/'ca.cer').read_bytes(),'application/pkix-cert');return
            if path in ('/connect','/admin/state','/qr.png'):
                if not self.loopback():self.fail('PC에서만 열 수 있는 화면입니다.',403);return
                if time.time()>gateway.pairing.expires:gateway.pairing.rotate()
                secure_url=f'https://{gateway.address}:{HTTPS_PORT}/m/#pair={gateway.pairing.nonce}'
                plain_url=f'http://{gateway.address}:{HTTP_PORT}/m/#pair={gateway.pairing.nonce}'
                if path=='/admin/state':
                    self.send(dict(address=gateway.address,phone_url=plain_url,secure_url=secure_url,pin=gateway.pairing.pin,expires=gateway.pairing.expires,
                                   paired=bool(gateway.pairing.device),push_enabled=bool(gateway.pairing.device and gateway.pairing.device.get('subscription')),fingerprint=gateway.keys['ca_fingerprint']));return
                if path=='/qr.png':
                    target=secure_url if 'secure=1' in self.path else plain_url;b=io.BytesIO();qrcode.make(target).save(b,format='PNG');self.send(b.getvalue(),'image/png');return
                markup=(ASSETS/'connect.html').read_text(encoding='utf-8').replace('{{IP}}',html.escape(gateway.address)).replace('{{PIN}}',gateway.pairing.pin).replace('{{HTTP_PORT}}',str(HTTP_PORT)).replace('{{HTTPS_PORT}}',str(HTTPS_PORT)).replace('{{FINGERPRINT}}',gateway.keys['ca_fingerprint'])
                self.send(markup.encode(),'text/html; charset=utf-8');return
            if path=='/m/api/state':
                if not self.authorized():self.fail('PC와 휴대폰을 먼저 연결해 주세요.',401);return
                self.send(gateway.state());return
            if path.startswith('/m/audio/'):
                if not self.authorized():self.fail('연결이 필요합니다.',401);return
                name=path.removeprefix('/m/audio/')
                if name not in {v+'.wav' for v in AUDIO_NAMES}:self.send_error(404);return
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8774/api/narration/audio/'+name,timeout=5) as r:audio=r.read()
                    self.send(audio,'audio/wav')
                except OSError:self.fail('음성을 준비하지 못했어요.',503)
                return
            files={'/m/':('index.html','text/html; charset=utf-8'),'/m/app.js':('app.js','application/javascript'),'/m/app.css':('app.css','text/css'),
                   '/m/sw.js':('sw.js','application/javascript'),'/m/manifest.webmanifest':('manifest.webmanifest','application/manifest+json'),'/m/icon.svg':('icon.svg','image/svg+xml'),
                   '/m/icon-192.png':('icon-192.png','image/png'),'/m/icon-512.png':('icon-512.png','image/png')}
            if path in ('/','/m'):self.send_response(302);self.send_header('Location','/m/');self.end_headers();return
            if path in files:
                name,kind=files[path];self.send((ASSETS/name).read_bytes(),kind);return
            self.send_error(404)
        def do_POST(self):
            if not self.check_host():self.fail('접속 주소를 확인해 주세요.',403);return
            expected=('https' if self.secure() else 'http')+'://'+self.headers['Host']
            origin=self.headers.get('Origin')
            if origin!=expected and not (origin is None and self.loopback()):self.fail('앱 화면에서 다시 시도해 주세요.',403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8192:raise ValueError('요청 크기를 확인해 주세요.')
                if 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('앱에서 다시 시도해 주세요.')
                body=json.loads(self.rfile.read(size));path=urlparse(self.path).path
                if not isinstance(body,dict):raise ValueError('요청 형식을 확인해 주세요.')
                if path=='/m/api/pair':
                    token=gateway.pairing.pair(str(body.get('code','')),self.client_address[0]);cookie=f'{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/m/; Max-Age=86400'+('; Secure' if self.secure() else '')
                    self.send(dict(paired=True),cookie=cookie);return
                if not self.authorized():self.fail('휴대폰 연결이 필요합니다.',401);return
                if path=='/m/api/command':self.send(gateway.command(body));return
                if path=='/m/api/subscribe':
                    if not self.secure() and not self.loopback():raise ValueError('시스템 알림은 HTTPS 홈 화면 앱에서 켜 주세요.')
                    gateway.pairing.subscribe(body.get('subscription'));self.send(dict(subscribed=True));return
                if path=='/m/api/unsubscribe':
                    with gateway.pairing.lock:gateway.pairing.device['subscription']=None;gateway.pairing.save()
                    self.send(dict(subscribed=False));return
                if path=='/m/api/push-test':
                    if not gateway.pairing.device.get('subscription'):raise ValueError('시스템 알림을 먼저 켜 주세요.')
                    gateway.deliver(dict(title='홍익 AI 알림 연결 확인',body='실제 주행 상황이 생기면 이곳으로 알려드릴게요.',tag='test-'+secrets.token_hex(4),url='/m/'))
                    self.send(dict(sent=gateway.push_error is None));return
                self.send_error(404)
            except (ValueError,TypeError,KeyError) as error:self.fail(str(error))
            except OSError:self.fail('PC와의 연결을 확인해 주세요.',503)
    return Handler


def main():
    gateway=Gateway();secure=ThreadingHTTPServer(('0.0.0.0',HTTPS_PORT),handler(gateway))
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(DATA/'server.pem',DATA/'server-key.pem');secure.socket=context.wrap_socket(secure.socket,server_side=True)
    gateway.tls_context=context
    plain=ThreadingHTTPServer(('0.0.0.0',HTTP_PORT),handler(gateway))
    threading.Thread(target=secure.serve_forever,daemon=True).start();threading.Thread(target=gateway.loop,daemon=True).start()
    print(f'Handset pairing: http://127.0.0.1:{HTTP_PORT}/connect',flush=True)
    try:plain.serve_forever()
    finally:gateway.stop.set();secure.shutdown();gateway.event_log.close()


if __name__=='__main__':main()
