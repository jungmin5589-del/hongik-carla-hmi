"""Publish explicit named/date-stamped CSV snapshots to the authorised public repo."""
import json,os,subprocess,threading,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
from research_store import experiment_date
REPO='jungmin5589-del/hongik-carla-hmi'
BRANCH='research-data'
URL='https://github.com/'+REPO

def snapshot(store):
    with store.lock,store.db() as db:
        dates=sorted({experiment_date(r[0]) for r in db.execute('SELECT COALESCE(started_utc,created_utc) FROM trials')})
        if not dates:raise ValueError('업로드할 실험 기록이 없습니다.')
        stamp=datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
        files={}
        for day in dates:
            for kind in ('trials','events'):files[f'exports/{day}/{stamp}/{kind}.csv']=store.export_csv(kind,day)
        manifest=dict(exported_at=datetime.now(timezone.utc).isoformat(),experiment_dates=dates,timezone='Asia/Seoul',counts=store.list()['counts'],includes_participant_names=True)
        files[f'exports/snapshots/{stamp}.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
        return files,manifest

def upload(store,files,manifest,runner=subprocess.run):
    work=store.root/'github-uploads'/uuid.uuid4().hex;work.mkdir(parents=True)
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
    def git(*args):
        r=runner(['git','-c','credential.https://github.com.username=jungmin5589-del',*args],cwd=work,env=env,capture_output=True,timeout=120,creationflags=0x08000000 if os.name=='nt' else 0)
        if r.returncode:raise RuntimeError('GitHub 연결 또는 쓰기 권한을 확인해 주세요. 자료는 PC에 보존했습니다.')
        return r.stdout.decode('utf-8',errors='replace').strip()
    git('init','--initial-branch='+BRANCH)
    git('remote','add','origin',URL+'.git')
    remote=git('ls-remote','--heads','origin','refs/heads/'+BRANCH)
    if remote:
        git('fetch','--depth=1','origin',BRANCH);git('checkout','-B',BRANCH,'FETCH_HEAD')
    for name,data in files.items():
        p=work/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    git('config','user.name','jungmin5589-del')
    git('config','user.email','258818090+jungmin5589-del@users.noreply.github.com')
    git('add','--',*files.keys())
    git('commit','-m','Save named experiment snapshot: '+', '.join(manifest['experiment_dates']))
    commit=git('rev-parse','HEAD');git('push','origin','HEAD:refs/heads/'+BRANCH)
    return dict(state='uploaded',url=URL+'/tree/'+BRANCH,commit=commit,experiment_dates=manifest['experiment_dates'],uploaded_at=manifest['exported_at'])

def start(store,confirmation):
    if confirmation!='이름과 실험 날짜 공개 업로드':raise ValueError('공개 업로드 확인이 필요합니다.')
    with store.lock:
        if store.github_status.get('state')=='uploading':raise ValueError('이미 GitHub에 업로드하고 있습니다.')
        files,manifest=snapshot(store);store.github_status={'state':'uploading','experiment_dates':manifest['experiment_dates']}
    def worker():
        try:store.github_status=upload(store,files,manifest)
        except (OSError,RuntimeError,subprocess.SubprocessError):store.github_status={'state':'error','error':'업로드하지 못했습니다. Git 설치·로그인·저장소 쓰기 권한을 확인해 주세요. PC 원본은 유지됩니다.'}
    threading.Thread(target=worker,name='research-github-upload',daemon=True).start()
    return dict(accepted=True,github=store.github_status)
