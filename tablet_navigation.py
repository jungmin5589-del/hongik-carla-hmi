"""Paired full cockpit on the existing LAN gateway, never a public CARLA API."""
import http.cookies
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse, unquote

ROOT = Path(__file__).resolve().parent
COOKIE = 'hongik_tablet'
BACKEND = 'http://127.0.0.1:8774'
STATIC = {'/cockpit.css','/cockpit.js','/driving-sound.css','/driving-sound.js',
 '/exterior-sound.js','/hongik-assistant.css','/language.js','/midterm-audio.js',
 '/midterm-panel.css','/midterm-panel.js','/multimodal.css','/nurec-map-context.js',
 '/nurec-nav-boot.js','/nurec-nav.css','/nurec-nav.js','/recorded-cabin.js',
 '/research-events.css','/research-events.js','/scene-audio.js','/underbody-sound.js',
 '/city-study.js','/city-study.css','/pedestrian-ui.js','/participant-setup.js','/feedback-voice.js'}
JSON_GET = {'/api/state','/api/atlas','/api/library','/api/language/en','/state',
 '/api/footsteps','/api/mechanical-audio','/api/recorded-cabin','/api/cabin-audio',
 '/api/participant/current','/api/research-voice','/api/language/zh'}
SOUNDS = re.compile(r'^/api/(?:narration/audio|english-audio|chinese-audio|research-audio)/[a-z_]+\.wav$')
MEDIA = re.compile(r'^/media/[a-zA-Z0-9_-]+$')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def backend(path, body=None, headers=None, method=None):
    # Callers only pass an enumerated route; never a client-supplied origin.
    request = urllib.request.Request(BACKEND+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json',**(headers or {})},method=method)
    return urllib.request.build_opener(NoRedirect).open(request,timeout=8)


def cookie_token(h, name):
    try:return http.cookies.SimpleCookie(h.headers.get('Cookie',''))[name].value
    except (KeyError,http.cookies.CookieError):return ''


def authenticated(h, gateway):
    return gateway.pairing.authenticate(cookie_token(h,COOKIE))


def redirect(h, target, cookie=None):
    h.send_response(302);h.send_header('Location',target)
    h.send_header('Cache-Control','no-store');h.send_header('Content-Length','0')
    if cookie:h.send_header('Set-Cookie',cookie)
    h.end_headers()


def cockpit_html(payload):
    text=payload.decode('utf-8')
    # Runs before the unchanged cockpit scripts on an ordinary LAN HTTP origin.
    script='<script src="/tablet-boot.js"></script>'
    return (text.replace('</head>',script+'</head>',1) if '</head>' in text
            else text.replace('<main>',script+'<main>',1)).encode()


def clean_script(payload, path):
    if path!='/nurec-nav.js':return payload
    text=payload.decode('utf-8')
    # Phone pairing and engine quality/reset controls remain on the operator PC.
    text='\n'.join(line for line in text.splitlines()
        if not line.lstrip().startswith(('const phone=document.createElement(',
                                         'for(const [tag,attr,url] of')))
    return text.replace("location.assign('http://127.0.0.1:8775/')","location.assign('/')").encode()


def safe_state(data):
    keys={'connected','schema','timestamp','frame','map','map_context','lane_width_m',
          'ego','road','actors','world_pose','destinations','route','session','passive','renderer'}
    value={key:data[key] for key in keys if key in data}
    raw=data.get('nurec',{})
    value['nurec']={key:raw[key] for key in ('kind','phase','mode','quality','width','height',
        'speed_kph','frames','scenario','error','lab_rig') if key in raw}
    return value


def serve(h, gateway, head=False):
    parsed=urlparse(h.path);path=parsed.path
    if path=='/m/navigation':
        token=cookie_token(h,'hongik_mobile')
        if gateway.pairing.authenticate(token):
            suffix='; Secure' if h.secure() else ''
            redirect(h,'/navigation'+('?' + parsed.query if parsed.query else ''),
                f'{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+suffix)
        else:h.send((ROOT/'tablet_connect.html').read_bytes(),'text/html; charset=utf-8')
        return True
    vendor=bool(re.fullmatch(r'/vendor/[A-Za-z0-9_.-]+\.(?:js|woff2)',path))
    icon=bool(re.fullmatch(r'/ui-assets/[A-Za-z0-9_-]+\.svg',path))
    audio=bool(SOUNDS.fullmatch(path)) or path in {'/api/footsteps/bank.wav',
        '/api/mechanical-audio/scrape.wav','/api/recorded-cabin/bank.wav','/api/cabin-audio/bank.wav'}
    media=bool(MEDIA.fullmatch(path))
    known=path in STATIC|JSON_GET|{'/','/navigation','/tablet-boot.js','/frame.jpg','/api/reply'} or vendor or icon or audio or media
    if not known:return False
    if not authenticated(h,gateway):
        if path=='/navigation':redirect(h,'/m/navigation'+('?' + parsed.query if parsed.query else ''));return True
        if cookie_token(h,COOKIE):h.fail('내비 연결이 만료됐어요. 다시 연결해 주세요.',401);return True
        return False  # Preserve companion-only routes and the old 404 boundary.
    try:
        if path=='/tablet-boot.js':h.send((ROOT/'tablet_boot.js').read_bytes(),'application/javascript');return True
        if path=='/api/state':h.send(safe_state(gateway.fetcher()));return True
        if path=='/api/reply':
            query=parse_qs(parsed.query);session=query.get('session',[''])[0];key=query.get('id',[''])[0]
            if session!=gateway.state().get('session') or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',key):
                raise ValueError('이전 주행의 요청입니다. 내비를 새로 열어 주세요.')
            target=path+'?'+urlencode({'session':session,'id':key})
        elif path=='/api/research-voice':
            lang=parse_qs(parsed.query).get('lang',['ko'])[0]
            target=path+'?'+urlencode({'lang':lang if lang in ('ko','en','zh') else 'ko'})
        else:target=path  # Asset cache tags are unnecessary; arbitrary queries stay local.
        if media or audio:
            headers={}
            if h.headers.get('Range'):headers['Range']=h.headers['Range']
            with backend(target,headers=headers,method='HEAD' if head and media else 'GET') as response:
                h.send_response(response.status)
                for name in ('Content-Type','Content-Length','Content-Range','Accept-Ranges'):
                    if response.headers.get(name):h.send_header(name,response.headers[name])
                h.send_header('Cache-Control','private, no-store');h.end_headers()
                if not head:
                    while True:
                        block=response.read(65536)
                        if not block:break
                        h.wfile.write(block)
            return True
        with backend(target) as response:
            payload=response.read(16*1024*1024+1);kind=response.headers.get('Content-Type','application/octet-stream')
        if len(payload)>16*1024*1024:raise ValueError('화면 자료가 너무 큽니다.')
        if path in ('/','/navigation'):payload=cockpit_html(payload)
        elif path=='/nurec-nav.js':payload=clean_script(payload,path)
        h.send(payload,kind);return True
    except urllib.error.HTTPError as error:
        h.fail('PC 화면 자료를 준비하지 못했어요.',error.code if error.code in (400,404,409,416) else 503)
    except (OSError,ValueError):h.fail('PC 주행 연결을 확인해 주세요.',503)
    return True


def post(h,gateway,body):
    path=urlparse(h.path).path
    if path not in ('/api/command','/control','/api/select','/api/participant'):return False
    if not authenticated(h,gateway):h.fail('전체 내비 연결이 필요합니다.',401);return True
    try:
        if path=='/api/command':h.send(gateway.queue_command(body,source='hongik_tablet'));return True
        state=gateway.state()
        if path=='/api/participant':
            if set(body)-{'name','language'}:raise ValueError('참가자 입력을 확인해 주세요.')
            clean=body
        elif path=='/control':
            if set(body)!={'mode','session_id'} or body.get('mode') not in ('auto','paused'):
                raise ValueError('엔진 초기화·화질 설정은 PC에서 해 주세요.')
            if not state.get('connected') or body['session_id']!=state.get('session'):
                raise ValueError('현재 주행 화면에서 다시 요청해 주세요.')
            clean=body
        else:
            if set(body)-{'profile','presentation','condition','language'} or body.get('profile') not in {
                'congestion','night','fog','yield','carpool','rattle','cargo'} or body.get('condition') not in ('A','B') or body.get('presentation')!='midterm':
                raise ValueError('주행 환경을 다시 선택해 주세요.')
            if state.get('connected') and state.get('elapsed_s',0)>0 and not state.get('completed'):
                raise ValueError('현재 주행이 끝난 뒤 다음 상황을 선택해 주세요.')
            clean=body
        with backend(path,body=clean) as response:h.send(json.load(response))
    except urllib.error.HTTPError as error:
        try:message=json.load(error).get('error')
        except (ValueError,AttributeError):message=None
        h.fail(message or 'PC가 요청을 반영하지 못했어요.',400)
    except ValueError as error:h.fail(str(error),400)
    except OSError:h.fail('PC 주행 연결을 확인해 주세요.',503)
    return True
