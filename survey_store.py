"""Versioned post-drive questionnaire, joined to the private trial/event database."""
import json
VERSION='post-drive-v1'
CORE=[('situation','어떤 상황이라고 이해했나요?','text'),('emotion','주행 중 어떤 감정이 들었나요?','text'),('wanted_request','차량에 어떤 대응을 요청하고 싶었나요?','text'),('anxiety','얼마나 불안했나요?','seven'),('frustration','얼마나 답답했나요?','seven'),('control','상황을 조절할 수 있다고 느꼈나요?','seven'),('understanding','차량의 행동을 이해할 수 있었나요?','seven')]
ON=[('notice','AI 알림을 알아챘나요?','notice'),('choice_reason','그 대응을 선택하거나 선택하지 않은 이유는 무엇인가요?','text'),('input_reason','그 입력 방법을 사용한 이유는 무엇인가요?','text'),('expected_result','예상한 결과와 실제 결과는 어떻게 달랐나요?','text'),('fit','요청과 차량의 대응이 잘 맞았나요?','five')]

def schema(ai=True):
 return dict(version=VERSION,questions=[dict(id=k,label=l,kind=t,required=t!='text') for k,l,t in CORE+(ON if ai else [])])

def init(store):
 with store.db() as db:db.execute('''CREATE TABLE IF NOT EXISTS surveys(trial_id TEXT PRIMARY KEY,schema_version TEXT NOT NULL,answers TEXT NOT NULL,saved_utc TEXT NOT NULL,submitted_utc TEXT,FOREIGN KEY(trial_id) REFERENCES trials(id))''')

def read(store,trial):
 with store.lock,store.db() as db:
  row=db.execute('SELECT * FROM surveys WHERE trial_id=?',(trial,)).fetchone()
 return dict(row,answers=json.loads(row['answers'])) if row else None

def validate(answers,ai,submit):
 if not isinstance(answers,dict):raise ValueError('설문 응답 형식을 확인해 주세요.')
 questions={q['id']:q for q in schema(ai)['questions']}
 if set(answers)-set(questions):raise ValueError('현재 회차의 설문 항목만 제출해 주세요.')
 clean={}
 for key,value in answers.items():
  kind=questions[key]['kind']
  if kind=='text':
   if not isinstance(value,str) or len(value)>1000:raise ValueError('서술형 답변은 1000자 이내로 입력해 주세요.')
   clean[key]=value
  elif value in ('',None):continue
  elif kind=='notice':
   if value not in ('yes','no','unsure'):raise ValueError('알림 응답을 선택해 주세요.')
   clean[key]=value
  elif kind=='five' and value=='na':clean[key]='na'
  else:
   if isinstance(value,bool) or str(value) not in [str(i) for i in range(1,8 if kind=='seven' else 6)]:raise ValueError('척도 범위 내에서 선택해 주세요.')
   clean[key]=int(value)
 if submit and any(q['required'] and q['id'] not in clean for q in questions.values()):raise ValueError('표시된 필수 척도 문항에 답해 주세요.')
 return clean

def save(store,trial,answers,ai,submit=False):
 from research_store import utc
 clean=validate(answers,ai,submit);now=utc()
 with store.lock,store.db() as db:
  t=db.execute('SELECT completed FROM trials WHERE id=?',(trial,)).fetchone()
  if not t or not t['completed']:raise ValueError('완료된 주행의 설문만 저장할 수 있어요.')
  previous=db.execute('SELECT submitted_utc FROM surveys WHERE trial_id=?',(trial,)).fetchone()
  if previous and previous['submitted_utc']:return read(store,trial)
  db.execute('INSERT INTO surveys VALUES(?,?,?,?,?) ON CONFLICT(trial_id) DO UPDATE SET answers=excluded.answers,saved_utc=excluded.saved_utc,submitted_utc=excluded.submitted_utc',(trial,VERSION,json.dumps(clean,ensure_ascii=False),now,now if submit else None))
 store.changed();return read(store,trial)

def current(bridge,body=None):
 sc=bridge.scenario
 if not sc or not sc.completed:raise ValueError('주행이 끝나면 설문을 작성할 수 있어요.')
 if body and body.get('session_id')!=sc.session:raise ValueError('주행이 변경됐어요. 현재 회차를 확인해 주세요.')
 setting=getattr(bridge,'experiment_spec',None) or {};ai=setting.get('ai_enabled',bridge.condition!='A');practice=bool(setting.get('practice'))
 registered=bool(getattr(sc,'research_participant_id',None))
 record=read(bridge.research,sc.session) if registered else getattr(sc,'test_survey',None)
 if body:
  if practice:raise ValueError('연습에는 설문이 없어요.')
  clean=validate(body.get('answers'),ai,body.get('submit') is True)
  if registered:
   bridge.research.flush_events();record=save(bridge.research,sc.session,clean,ai,body.get('submit') is True)
  else:
   from research_store import utc
   if not record or not record.get('submitted_utc'):
    record=dict(answers=clean,submitted_utc=utc() if body.get('submit') is True else None);sc.test_survey=record
 return dict(session_id=sc.session,required=not practice,recording=registered,schema=schema(ai),record=record,profile=bridge.profile,condition='AI_ON' if ai else 'AI_OFF')

def pending(bridge):
 sc=bridge.scenario
 if not sc or not sc.completed or not getattr(sc,'research_participant_id',None):return False
 if (getattr(bridge,'experiment_spec',None) or {}).get('practice'):return False
 record=read(bridge.research,sc.session)
 return not record or not record.get('submitted_utc')

def export_csv(store,date=None):
 import csv,io
 from research_store import safe_csv,experiment_date
 keys=[k for k,_,_ in CORE+ON]
 with store.lock,store.db() as db:
  rows=db.execute('SELECT s.*,t.profile,t.condition,t.language,t.started_utc,t.created_utc,p.name FROM surveys s JOIN trials t ON t.id=s.trial_id JOIN participants p ON p.id=t.participant_id ORDER BY s.saved_utc').fetchall()
 out=io.StringIO(newline='');w=csv.writer(out);w.writerow(['experiment_date','participant','trial_id','scenario','condition','language','schema_version','saved_utc','submitted_utc',*keys])
 for r in rows:
  day=experiment_date(r['started_utc'] or r['created_utc'])
  if date and day!=date:continue
  a=json.loads(r['answers']);w.writerow([safe_csv(x) for x in [day,r['name'],r['trial_id'],r['profile'],r['condition'],r['language'],r['schema_version'],r['saved_utc'],r['submitted_utc'],*(a.get(k) for k in keys)]])
 return out.getvalue().encode('utf-8-sig')
