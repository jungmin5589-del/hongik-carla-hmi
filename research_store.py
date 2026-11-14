"""Participant records live on the internal disk, outside the public code repo."""
import csv,io,json,os,shutil,sqlite3,threading,time,uuid,queue
from contextlib import contextmanager,closing
from datetime import datetime,timezone,timedelta
from pathlib import Path

PROFILES={'congestion':'4차로 정체','night':'졸음운전 앞차','fog':'짙은 안개',
 'yield':'보행자 양보','carpool':'카풀 대기','rattle':'반복 이상음','cargo':'낙하물'}
DEFAULT_ROOT=Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'HongikDriveResearch'
FOLDER_NAME='홍익 주행 실험 기록'
MARKER='.hongik-research-target.json'
def utc():return datetime.now(timezone.utc).isoformat()
def experiment_date(value):
    if not value:return ''
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=9))).date().isoformat()
def safe_csv(value):
    value='' if value is None else str(value)
    return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value

class ResearchStore:
    def __init__(self,root=DEFAULT_ROOT,start_worker=True):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'research.sqlite3';self.config_path=self.root/'drive-config.json'
        self.lock=threading.RLock();self.export_lock=threading.Lock();self.wake=threading.Event();self.stop=threading.Event()
        self.dirty=True;self.current=None;self.error='';self.sync_info={};self.heartbeat={}
        self.github_status={'state':'idle'}
        with self.db() as db:db.executescript('''
CREATE TABLE IF NOT EXISTS participants(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trials(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL,profile TEXT NOT NULL,
 condition TEXT,language TEXT,created_utc TEXT,started_utc TEXT,finished_utc TEXT,onset_s REAL,
 selected_s REAL,executed_s REAL,last_action TEXT,result TEXT,completed INTEGER DEFAULT 0,
 FOREIGN KEY(participant_id) REFERENCES participants(id));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,trial_id TEXT NOT NULL,
 utc TEXT NOT NULL,elapsed_s REAL NOT NULL,since_onset_s REAL,wall_since_start_s REAL,
 event TEXT NOT NULL,action TEXT,label TEXT,details TEXT,
 FOREIGN KEY(trial_id) REFERENCES trials(id));
CREATE INDEX IF NOT EXISTS event_trial ON events(trial_id,id);
''')
        self.worker=None;self.event_worker=None;self.event_queue=queue.Queue()
        if start_worker:
            self.event_worker=threading.Thread(target=self._events_loop,daemon=True);self.event_worker.start()
            self.worker=threading.Thread(target=self._loop,daemon=True);self.worker.start()
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA foreign_keys=ON')
            yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()
    def changed(self):self.dirty=True;self.wake.set()
    def participant(self,name):
        if not isinstance(name,str) or not name.strip() or len(name.strip())>80 or any(ord(c)<32 for c in name):
            raise ValueError('참가자 이름 또는 ID를 1~80자로 입력해 주세요.')
        value=dict(id=uuid.uuid4().hex,name=name.strip(),created_utc=utc())
        with self.lock,self.db() as db:
            db.execute('INSERT INTO participants VALUES(:id,:name,:created_utc)',value)
            self.current=value;self.changed()
        return dict(value)
    def current_participant(self):return dict(self.current) if self.current else None
    def attach(self,scenario,profile,condition,language='ko'):
        participant=self.current_participant()
        scenario.research_participant_id=participant['id'] if participant else None
        if participant is None:return  # Unregistered developer sessions stay in their original JSONL logs.
        labels={o['action']:o['label'] for o in __import__('midterm_study').OPTIONS.get(profile,[])}
        labels.update(study_maintain='그냥 둘게요',study_fixed_help='도움 요청',study_fixed_stop='정차 요청')
        with self.lock,self.db() as db:
            db.execute('INSERT OR IGNORE INTO trials(id,participant_id,profile,condition,language,created_utc) VALUES(?,?,?,?,?,?)',
                (scenario.session,participant['id'],profile,condition,language,utc()))
        original=scenario.log
        def logged(event,**extra):
            original(event,**extra)
            try:
                occurred=(utc(),time.monotonic())
                if self.event_worker is not None:
                    frozen=dict(extra)
                    if isinstance(extra.get('client_event'),dict):frozen['client_event']=dict(extra['client_event'])
                    self.event_queue.put_nowait((scenario.session,event,scenario.elapsed,frozen,labels,occurred))
                else:self.event(scenario.session,event,scenario.elapsed,extra,labels,occurred)
            except (OSError,sqlite3.Error) as error:self.error='기록 오류: '+type(error).__name__
        scenario.log=logged;self.changed()
    def start(self,session):
        with self.lock,self.db() as db:
            row=db.execute('SELECT started_utc FROM trials WHERE id=?',(session,)).fetchone()
            if row and not row['started_utc']:
                db.execute('UPDATE trials SET started_utc=? WHERE id=?',(utc(),session))
                self.heartbeat[session]=time.monotonic();self.changed()
    def event(self,session,event,elapsed,extra,labels=None,occurred=None):
        recorded_utc,recorded_monotonic=occurred or (utc(),time.monotonic())
        labels=labels or {};details=extra.get('client_event') or {}
        action=extra.get('action') or details.get('choice')
        # Store only study meaning, not tokens, browser/device IDs or world coordinates.
        approved={key:extra[key] for key in ('status','condition','summary','count','repeat_count','reason') if key in extra}
        for key in ('phase','options_visible','event_visible'):
            if key in details:approved[key]=details[key]
        with self.lock,self.db() as db:
            trial=db.execute('SELECT * FROM trials WHERE id=?',(session,)).fetchone()
            if not trial:return
            onset=trial['onset_s']
            if event in ('scenario_onset','weaving_started') and onset is None:
                onset=float(elapsed);db.execute('UPDATE trials SET onset_s=? WHERE id=?',(onset,session))
            canonical=action if action and action.startswith('study_') else 'study_'+action if action else None
            label=labels.get(canonical,canonical or '')
            wall=recorded_monotonic-self.heartbeat[session] if session in self.heartbeat else None
            db.execute('INSERT INTO events(trial_id,utc,elapsed_s,since_onset_s,wall_since_start_s,event,action,label,details) VALUES(?,?,?,?,?,?,?,?,?)',
                (session,recorded_utc,float(elapsed),None if onset is None else float(elapsed)-onset,wall,event,canonical,label,json.dumps(approved,ensure_ascii=False)))
            if event=='navigation_study_choice':db.execute('UPDATE trials SET selected_s=COALESCE(selected_s,?),last_action=? WHERE id=?',(elapsed,canonical,session))
            if event=='navigation_execution_confirmed':db.execute('UPDATE trials SET executed_s=COALESCE(executed_s,?),last_action=? WHERE id=?',(elapsed,canonical,session))
            if event in ('request_completed','outcome_trial_completed','trial_completed'):
                db.execute('UPDATE trials SET completed=1,finished_utc=?,result=? WHERE id=?',(recorded_utc,extra.get('status') or extra.get('reason') or 'complete',session))
            self.changed()
    def list(self,search=''):
        search=str(search)[:100]
        with self.lock,self.db() as db:
            trials=[dict(row) for row in db.execute('''SELECT t.*,p.name participant_name,
 (SELECT label FROM events WHERE trial_id=t.id AND event='navigation_study_choice' ORDER BY id LIMIT 1) first_choice,
 (SELECT COUNT(*) FROM events WHERE trial_id=t.id AND event='navigation_study_choice') selection_count,
 t.selected_s-t.onset_s selected_after_onset_s
 FROM trials t JOIN participants p ON t.participant_id=p.id
 WHERE p.name LIKE ? OR t.profile LIKE ? ORDER BY t.created_utc DESC LIMIT 500''',('%'+search+'%','%'+search+'%'))]
            counts=dict(participants=db.execute('SELECT COUNT(*) FROM participants').fetchone()[0],trials=db.execute('SELECT COUNT(*) FROM trials').fetchone()[0],events=db.execute('SELECT COUNT(*) FROM events').fetchone()[0])
        for row in trials:
            row['scenario_name']=PROFILES.get(row['profile'],row['profile'])
            row['experiment_date']=experiment_date(row['started_utc'] or row['created_utc'])
        return dict(trials=trials,counts=counts,sync=self.sync_status(),recording_error=self.error,github=self.github_status)
    def detail(self,trial):
        with self.lock,self.db() as db:
            return [dict(row) for row in db.execute('SELECT * FROM events WHERE trial_id=? ORDER BY id',(trial,))]
    def export_csv(self,kind='trials',date=None):
        if kind not in ('trials','events'):raise ValueError('Unknown export')
        with self.lock,self.db() as db:
            if kind=='trials':cursor=db.execute('''SELECT COALESCE(t.started_utc,t.created_utc) _experiment_utc,p.name participant,t.id trial,t.profile scenario,t.condition,t.language,
 t.started_utc,t.onset_s,t.selected_s selected_after_start_s,t.selected_s-t.onset_s selected_after_onset_s,
 t.executed_s executed_after_start_s,t.last_action,t.result,t.finished_utc,t.completed
 FROM trials t JOIN participants p ON p.id=t.participant_id ORDER BY t.created_utc''')
            else:cursor=db.execute('''SELECT COALESCE(t.started_utc,t.created_utc) _experiment_utc,p.name participant,t.profile scenario,t.condition,t.language,e.*
 FROM events e JOIN trials t ON t.id=e.trial_id JOIN participants p ON p.id=t.participant_id ORDER BY e.id''')
            headers=[v[0] for v in cursor.description];rows=cursor.fetchall()
        output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(['experiment_date']+headers[1:])
        for row in rows:
            day=experiment_date(row[0])
            if date is None or day==date:writer.writerow([day]+[safe_csv(v) for v in row[1:]])
        return output.getvalue().encode('utf-8-sig')
    def reset(self,confirmation,expected):
        if confirmation!='초기화':raise ValueError('초기화를 입력해 주세요.')
        self.flush_events()
        with self.lock:
            if self.github_status.get('state')=='uploading':raise ValueError('GitHub 업로드가 끝난 뒤 초기화해 주세요.')
            counts=self.list()['counts']
            if counts!=expected:raise ValueError('기록 수가 변경됐습니다. 새로고침 후 다시 확인해 주세요.')
            backup=self.root/'reset-backups'/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
            backup.mkdir(parents=True)
            with self.db() as source,closing(sqlite3.connect(backup/'research.sqlite3')) as dest:source.backup(dest)
            for kind in ('trials','events'):(backup/(kind+'.csv')).write_bytes(self.export_csv(kind))
            with self.db() as db:
                db.execute('DELETE FROM events');db.execute('DELETE FROM trials');db.execute('DELETE FROM participants')
            self.current=None;self.heartbeat.clear();self.error='';self.changed()
        self.export()
        return dict(reset=True,backup=str(backup),previous_counts=counts)
    def sync_status(self):
        config=json.loads(self.config_path.read_text('utf-8')) if self.config_path.exists() else {}
        return dict(self.sync_info,pending_records=self.event_queue.unfinished_tasks,configured=bool(config),folder_url=config.get('folder_url'),local_path=str(self.path))
    def find_target(self,config):
        candidates=[]
        if config.get('directory'):candidates.append(Path(config['directory']))
        for letter in 'GHIJKLMNOPQRSTUVWXYZEF':
            for label in ('My Drive','내 드라이브'):
                candidates.append(Path(letter+':/')/label/FOLDER_NAME)
        candidates.extend(Path.home()/label/FOLDER_NAME for label in ('Google Drive','My Drive','내 드라이브'))
        for target in candidates:
            marker=target/MARKER
            try:
                value=json.loads(marker.read_text('utf-8'))
                if value.get('folder_id')==config.get('folder_id') and value.get('marker')==config.get('marker'):return target
            except (OSError,ValueError):continue
        return None
    def export(self):
        with self.export_lock:self._export()
    def _export(self):
        self.flush_events()
        folder=self.root/'exports';folder.mkdir(exist_ok=True)
        with self.lock:self.dirty=False
        # CSV encoding and filesystem/Drive work must not hold the record lock.
        for kind in ('trials','events'):
            temp=folder/(kind+'.tmp');temp.write_bytes(self.export_csv(kind));os.replace(temp,folder/(kind+'.csv'))
        temporary=folder/'research.tmp.sqlite3'
        with self.lock,self.db() as source,closing(sqlite3.connect(temporary)) as target:source.backup(target)
        os.replace(temporary,folder/'research.sqlite3')
        self.sync_info.update(exported_utc=utc(),error=None)
        if not self.config_path.exists():self.sync_info['state']='local-only';return
        config=json.loads(self.config_path.read_text('utf-8'));target=self.find_target(config)
        if target is None:self.sync_info['state']='waiting-for-drive-desktop';return
        for item in folder.iterdir():
            if item.suffix not in ('.csv','.sqlite3'):continue
            temp=target/(item.name+'.uploading');shutil.copyfile(item,temp);os.replace(temp,target/item.name)
        self.sync_info.update(state='written-to-drive-folder',mirrored_utc=utc())
    def _loop(self):
        while not self.stop.is_set():
            self.wake.wait(5);self.wake.clear()
            if self.stop.wait(1):break
            if not self.dirty and self.sync_info.get('state') not in ('waiting-for-drive-desktop','error'):continue
            try:self.export()
            except (OSError,ValueError,sqlite3.Error) as error:self.sync_info.update(state='error',error=type(error).__name__)
    def _events_loop(self):
        while True:
            entry=self.event_queue.get()
            try:
                if entry is None:return
                self.event(*entry)
            except (OSError,sqlite3.Error) as error:self.error='기록 오류: '+type(error).__name__
            finally:self.event_queue.task_done()
    def flush_events(self):self.event_queue.join()
    def close(self):
        if self.event_worker:
            self.event_queue.put(None);self.event_worker.join(5)
        self.stop.set();self.wake.set()
