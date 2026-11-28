"""UI-only lab update: never replace motion/vehicle controllers or the Rust DLL."""
import argparse,hashlib,json,shutil,socket,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FILES=('course_ui/index.html','course_ui/vendor/Geist-LICENSE.txt',
 'course_ui/vendor/Geist-Variable.woff2','course_ui/vendor/GeistMono-Variable.woff2',
 'course_ui/vendor/ko-typeset.css','course_ui/vendor/ko-typeset.js','course_ui/vendor/operator-geist.css',
 'drive.html','experiment.html','experiment_ui.js','midterm_panel.css','midterm_panel.js',
 'native_home.html','participant_setup.js','research_admin.html','survey_ui.js','runtime_version.py')
PROTECTED=('vehicle_following.py','motion_link.py','lab.local.json','settings/portable-motion.json',
 '../data-server-py/collector/carla_collector.py','../data-server-py/processing/transforms_A.py',
 '../data-server-py/sixdof_rs.pyd','data-server-py/collector/carla_collector.py',
 'data-server-py/processing/transforms_A.py','data-server-py/sixdof_rs.pyd')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def plan(target,source=ROOT):
 target,source=Path(target).resolve(),Path(source).resolve()
 if target==source:raise ValueError('Select the runtime live folder, not this source checkout')
 if not (target/'native_carla.py').is_file():raise ValueError('Existing CARLA live folder required')
 pending=[]
 for name in FILES:
  data=(source/name).read_bytes();p=target/name
  if not p.exists() or p.read_bytes()!=data:pending.append((p,data,name))
 # Only patch the two presentation-serving lines in field-modified Python.
 patches=[('navigation_adapter.py',"path.endswith(('.js', '.woff2'))","path.endswith(('.js', '.css', '.woff2'))"),
  ('native_carla.py','<main><p><a href="/experiment">AI OFF / ON experiment</a></p>','<main>')]
 for name,old,new in patches:
  p=target/name;text=p.read_text('utf-8')
  if old in text:
   if text.count(old)!=1:raise ValueError('Ambiguous server patch: '+name)
   raw=p.read_bytes();data=raw.replace(old.encode(),new.encode());pending.append((p,data,name))
  elif new not in text:raise ValueError('Unrecognized server version; compare manually: '+name)
 return pending
def apply(target,write=False,source=ROOT):
 target=Path(target).resolve();pending=plan(target,source)
 before={n:sha(target/n) for n in PROTECTED}
 if not write:return dict(check=True,changed=[n for _,_,n in pending],protected=before)
 for port in (2016,2026,8774,8765):
  with socket.socket() as c:
   c.settimeout(.2)
   if c.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Close the driving app normally first (port '+str(port)+')')
 backup=target/'backups'/('passenger-ui-20261128-'+uuid.uuid4().hex)
 for p,data,name in pending:
  if p.is_file():
   old=backup/name;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,old)
 for p,data,name in pending:
  p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.installing');tmp.write_bytes(data);tmp.replace(p)
 if {n:sha(target/n) for n in PROTECTED}!=before:raise RuntimeError('Protected lab file changed')
 if not all(p.read_bytes()==data for p,data,_ in pending):raise RuntimeError('UI verification failed')
 report=dict(applied=True,changed=[n for _,_,n in pending],backup=str(backup),protected_unchanged=True,
             field_motion_patch_verified=False)
 backup.mkdir(parents=True,exist_ok=True);(backup/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--target-live',required=True,type=Path)
 p.add_argument('--apply',action='store_true');a=p.parse_args()
 print(json.dumps(apply(a.target_live,a.apply),ensure_ascii=False,indent=2))
