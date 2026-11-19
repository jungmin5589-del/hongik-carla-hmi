"""Local-only CPU STT worker. Raw audio is temporary and never exported."""
import base64,json,threading,time,uuid,tempfile,os,io,wave
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
state={'state':'loading','model':'small','device':'cpu','compute_type':'int8'};model=None;jobs={};lock=threading.Lock();jobs_lock=threading.Lock()
def load():
 global model
 try:
  from faster_whisper import WhisperModel
  model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4,num_workers=1)
  state['state']='ready'
 except Exception as e:state.update(state='error',error=type(e).__name__+': '+str(e)[:200])
def transcribe(key,data,language):
 start=time.monotonic();path=None
 try:
  with tempfile.NamedTemporaryFile(suffix='.wav',delete=False) as f:f.write(data);path=f.name
  with lock:
   segments,info=model.transcribe(path,language=language,beam_size=1,vad_filter=True,condition_on_previous_text=False,initial_prompt='앞차, 차간 거리, 차로, 추월, 경적, 틈이 생기면 알려 줘.')
   text=''.join(s.text for s in segments).strip()
  jobs[key]=dict(state='done',text=text,processing_ms=round((time.monotonic()-start)*1000),model='small-cpu-int8')
 except Exception as e:jobs[key]=dict(state='error',error=type(e).__name__)
 finally:
  if path:os.unlink(path)
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,obj,status=200):
  b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):self.send(dict(service='hongik-local-stt',**state) if self.path=='/health' else jobs.get(self.path.split('/')[-1],{'state':'missing'}))
 def do_POST(self):
  try:
   if self.headers.get('Origin') is not None:return self.send({'error':'Local proxy required'},403)
   n=int(self.headers.get('Content-Length',0))
   if self.path!='/transcribe' or not 0<n<=3000000:raise ValueError('Invalid audio request')
   d=json.loads(self.rfile.read(n))
   if not isinstance(d,dict) or not isinstance(d.get('audio'),str):raise ValueError('Invalid audio request')
   audio=base64.b64decode(d['audio'],validate=True)
   if state['state']!='ready':return self.send({'error':'음성 모델 준비 중이에요.'},503)
   if not audio.startswith(b'RIFF') or len(audio)>2200000:raise ValueError('WAV audio required')
   with wave.open(io.BytesIO(audio)) as w:
    if w.getnchannels()!=1 or w.getsampwidth()!=2 or not 8000<=w.getframerate()<=48000 or not 0<w.getnframes()/w.getframerate()<=12:raise ValueError('Short mono PCM audio required')
   with jobs_lock:
    if any(j.get('state')=='running' for j in jobs.values()):return self.send({'error':'이전 음성을 처리하고 있어요.'},409)
    if len(jobs)>=20:jobs.pop(next(iter(jobs)))
    key=uuid.uuid4().hex;jobs[key]={'state':'running'}
   threading.Thread(target=transcribe,args=(key,audio,d.get('language','ko') if d.get('language','ko') in ('ko','en','zh') else 'ko'),daemon=True).start();self.send({'job':key})
  except (ValueError,TypeError,KeyError,wave.Error,EOFError):self.send({'error':'녹음 파일을 확인해 주세요.'},400)
if __name__=='__main__':
 s=ThreadingHTTPServer(('127.0.0.1',8792),H);threading.Thread(target=load,daemon=True).start();s.serve_forever()
