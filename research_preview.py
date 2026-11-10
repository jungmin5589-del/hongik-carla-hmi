"""Isolated UI/DB/audio fixture. Never connects to or controls CARLA."""
import copy,io,json,queue,tempfile,threading,uuid
from types import SimpleNamespace
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
import native_carla
from preview_language import fixture
from research_store import ResearchStore

class Preview:
 def __init__(self,folder):
  self.lock=threading.RLock();self.research=ResearchStore(folder,start_worker=False)
  self.language='ko';self.condition='B';self.presentation='midterm';self.scenario=None
  self.state=dict(phase='choose',profile='night',frames=3,width=1280,height=720,measured_fps=0)
  self.snapshot=fixture();self.snapshot['connected']=False;self.command={'mode':'paused'}
  self.pending=SimpleNamespace(put=self.select)
  self.navigation=SimpleNamespace(state=lambda:copy.deepcopy(self.snapshot),atlas=lambda:dict(map='CARLA',roads=[],destinations=[],buildings=[]),command=self.request,reply=lambda *args:dict(accepted=True,message='fixture response'))
  buffer=io.BytesIO();Image.new('RGB',(16,9),'#e9edf2').save(buffer,'JPEG');self.jpeg=buffer.getvalue()
 def select(self,value):
  _,profile=value;sid='qa-'+uuid.uuid4().hex[:10];self.profile=profile
  sc=SimpleNamespace(session=sid,elapsed=0.,completed=False,log=lambda *a,**k:None)
  self.scenario=sc;self.research.attach(sc,profile,self.condition,self.language)
  self.snapshot=fixture();self.snapshot['session']['session_id']=sid;self.snapshot['session']['stage']='ready';self.snapshot['session']['navigation']['id']=sid+'-weaving'
  self.snapshot['session']['navigation']['research_event']['active']=False;self.snapshot['session']['navigation']['research_event']['condition']=self.condition
  self.snapshot['nurec']['scenario'].update(session=sid,elapsed_s=0.,onset=False);self.snapshot['nurec']['mode']='paused'
  self.state.update(phase='live',profile=profile);sc.public=lambda:copy.deepcopy(self.snapshot['nurec']['scenario'])
 def control(self,body):
  self.command['mode']=body.get('mode','paused');self.snapshot['nurec']['mode']=self.command['mode']
  if self.command['mode']=='auto':
   self.research.start(self.scenario.session);self.scenario.elapsed=10.;self.scenario.log('scenario_onset')
   self.snapshot['session']['stage']='running';self.snapshot['session']['navigation']['research_event']['active']=True
   self.snapshot['nurec']['scenario'].update(elapsed_s=10.,onset=True)
  return dict(accepted=True)
 def change_phase(self,phase):
  with self.lock:
   e=self.snapshot['session']['navigation']['research_event'];e['study'].update(phase=phase,action='horn');e['pending']=phase not in ('idle','complete');e['active']=False
   e['outcome'].update(phase=phase,status='achieved',summary='경적을 한 번 짧게 울렸어요. 앞차의 움직임을 살피며 주행했어요.')
   if phase=='complete':
    self.scenario.elapsed=30.;self.scenario.completed=True;self.scenario.log('request_completed',action='horn',status='achieved')
    self.snapshot['nurec']['scenario'].update(completed=True,elapsed_s=30.);self.snapshot['nurec']['mode']='paused';self.research.export()
 def request(self,body):
  action=body['action'];details=body.get('client_event') or {};sc=self.scenario
  if action=='study_choice':sc.elapsed=17.25;sc.log('navigation_study_choice',client_event=details)
  elif action=='study_horn':
   sc.elapsed=18.;sc.log('navigation_execution_confirmed',action=action,client_event=details)
   self.change_phase('queued');threading.Timer(1.5,lambda:self.change_phase('applying')).start();threading.Timer(4,lambda:self.change_phase('observing')).start();threading.Timer(9,lambda:self.change_phase('complete')).start()
  else:sc.log('navigation_'+action,client_event=details)
  return dict(session_id=sc.session,command_id='qa-command')

def main():
 temporary=tempfile.TemporaryDirectory();bridge=Preview(Path(temporary.name))
 server=ThreadingHTTPServer(('127.0.0.1',0),native_carla.handler(bridge));native_carla.PORT=server.server_port
 print('PREVIEW='+json.dumps({'port':server.server_port}),flush=True)
 try:server.serve_forever()
 finally:bridge.research.close();server.server_close();temporary.cleanup()
if __name__=='__main__':main()
