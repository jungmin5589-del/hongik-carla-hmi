"""Local HTTP boundaries and asynchronous transcript jobs; fake acoustic model."""
import base64,io,json,threading,time,unittest,urllib.request,urllib.error,wave
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import stt_service as stt
class STTTests(unittest.TestCase):
 def setUp(self):
  stt.jobs.clear();self.patches=[patch.object(stt,'state',{'state':'ready'}),patch.object(stt,'model',SimpleNamespace(transcribe=lambda *a,**k:([SimpleNamespace(text='앞차와 거리 더 넓혀 줘')],None)))]
  for p in self.patches:p.start()
  self.server=ThreadingHTTPServer(('127.0.0.1',0),stt.H);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.url='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):
  self.server.shutdown();self.server.server_close()
  for p in self.patches:p.stop()
 def call(self,path,body=None,origin=None):
  h={'Content-Type':'application/json'}
  if origin:h['Origin']=origin
  r=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
  try:
   with urllib.request.urlopen(r) as f:return f.status,json.load(f)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def audio(self,seconds=1):
  b=io.BytesIO()
  with wave.open(b,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*16000*seconds)
  return {'audio':base64.b64encode(b.getvalue()).decode(),'language':'ko'}
 def test_short_job_and_poll(self):
  code,d=self.call('/transcribe',self.audio());self.assertEqual(code,200)
  until=time.monotonic()+2
  while time.monotonic()<until:
   code,j=self.call('/jobs/'+d['job'])
   if j['state']=='done':break
   time.sleep(.01)
  self.assertEqual(j['text'],'앞차와 거리 더 넓혀 줘');self.assertIn('processing_ms',j)
 def test_invalid_and_long_audio(self):
  for d in ([],{},self.audio(13),{'audio':'not base64'}):self.assertEqual(self.call('/transcribe',d)[0],400)
 def test_cross_origin_rejected(self):self.assertEqual(self.call('/transcribe',self.audio(),'https://unrelated.test')[0],403)
 def test_single_active_job(self):
  stt.jobs['one']={'state':'running'};self.assertEqual(self.call('/transcribe',self.audio())[0],409)
 def test_completed_trial_does_not_block_reusing_preloaded_model(self):
  from stt_proxy import proxy_post
  with patch('stt_proxy.call',return_value={'service':'hongik-local-stt','state':'ready'}):
   result=proxy_post('/api/stt/start',{},SimpleNamespace(command={'mode':'auto'},scenario=SimpleNamespace(completed=True)))
   self.assertEqual(result['state'],'ready')
if __name__=='__main__':unittest.main()
