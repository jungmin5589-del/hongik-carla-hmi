"""No cloud transmission; forward to the dedicated localhost STT process."""
import json,urllib.request,urllib.error,subprocess,os
from pathlib import Path
def call(path,body=None):
 try:
  r=urllib.request.Request('http://127.0.0.1:8792'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(r,timeout=3) as f:return json.load(f)
 except urllib.error.HTTPError as error:
  try:return json.load(error)
  except ValueError:return {'error':'음성 요청을 확인해 주세요.'}
 except (OSError,ValueError):return {'state':'unavailable','error':'로컬 STT가 준비되지 않았어요. 실험 준비 화면에서 모델을 켜 주세요.'}
def proxy_get(path):return call('/health' if path=='/api/stt/status' else '/jobs/'+path.split('/')[-1])
def proxy_post(path,body,bridge):
 if path=='/api/stt/start':
  if bridge.command.get('mode')=='auto' and not getattr(getattr(bridge,'scenario',None),'completed',False):raise ValueError('주행을 멈춘 뒤 음성 모델을 준비해 주세요.')
  status=call('/health')
  if status.get('service')=='hongik-local-stt':return status
  import socket
  with socket.socket() as s:
   if s.connect_ex(('127.0.0.1',8792))==0:raise ValueError('다른 서비스가 음성 포트를 사용하고 있어요.')
  py=Path(os.environ['LOCALAPPDATA'])/'HongikSTT/venv/Scripts/python.exe'
  if not py.exists():raise ValueError('로컬 STT 설치를 먼저 실행해 주세요.')
  subprocess.Popen([str(py),str(Path(__file__).with_name('stt_service.py'))],creationflags=0x08000000,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  return {'state':'loading','message':'무료 로컬 모델을 준비하고 있어요. 첫 실행은 다운로드가 필요해요.'}
 if path!='/api/stt/transcribe':raise ValueError('Unknown STT operation')
 return call('/transcribe',body)
