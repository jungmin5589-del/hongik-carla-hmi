"""Build source + reviewed cached audio update. No models, personal data or music."""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from apply_team_update import AUDIO,approved
from deploy_nurec_option import source_bytes
from repo_safety import allowed,check_content

ROOT=Path(__file__).resolve().parent
NAME='Hongik-Experiment-Update-20261122'

def inline(text):
    value=html.escape(text)
    def link(match):
        label,url=match.groups()
        if not url.startswith(('https://','http://')):
            url='https://github.com/jungmin5589-del/hongik-carla-hmi/blob/codex/portable-motion-20261111/docs/'+url
        return '<a href="'+url+'">'+label+'</a>'
    value=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,value)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',value)

def guide_html():
    lines=(ROOT/'docs/TEAM-START-HERE-KO.md').read_text('utf-8').splitlines()
    blocks=[];listing=None;code=None;table=False
    for line in lines+['']:
        if line.startswith('```'):
            if code is None:code=[]
            else:blocks.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');code=None
            continue
        if code is not None:code.append(line);continue
        list_match=re.match(r'^(?:([-])|\d+\.) (.*)',line)
        kind=('ul' if list_match.group(1) else 'ol') if list_match else None
        if listing and kind!=listing:blocks.append('</'+listing+'>');listing=None
        if table and not line.startswith('|'):blocks.append('</tbody></table></div>');table=False
        if not line.strip():continue
        if line.startswith('|'):
            if re.fullmatch(r'[| :\-]+',line):continue
            cells=[inline(c.strip()) for c in line.strip('|').split('|')]
            if not table:
                blocks.append('<div class="table"><table><thead><tr>'+''.join('<th>'+c+'</th>' for c in cells)+'</tr></thead><tbody>');table=True
            else:blocks.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
        elif list_match:
            if not listing:listing=kind;blocks.append('<'+kind+'>')
            blocks.append('<li>'+inline(list_match.group(2))+'</li>')
        elif line.startswith('#'):
            level=len(line)-len(line.lstrip('#'));blocks.append(f'<h{level}>'+inline(line[level:].strip())+f'</h{level}>')
        else:blocks.append('<p>'+inline(line)+'</p>')
    css='''@font-face{font-family:Pretendard;src:url("course_ui/vendor/PretendardVariable.woff2")}@font-face{font-family:Guide;src:url("files/live/course_ui/vendor/PretendardVariable.woff2")}
*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#192333;font-family:Pretendard,Guide,"Malgun Gothic",sans-serif;font-weight:500;line-height:1.8}header{padding:20px max(24px,calc((100vw - 1000px)/2));background:white;border-bottom:1px solid #e1e6ef;font-size:12px;font-weight:800;letter-spacing:.13em;color:#4169e6}main{max-width:1048px;margin:40px auto;padding:40px 44px;background:white;border:1px solid #e8ecf2;border-radius:24px}h1{font-size:34px;font-weight:800;letter-spacing:-.05em;line-height:1.3;margin:0 0 24px}h2{font-size:22px;font-weight:800;letter-spacing:-.04em;margin:48px 0 18px;padding-top:22px;border-top:1px solid #e9edf3}p,li{font-size:15px}strong{font-weight:750;color:#1c355e}a{color:#4169e6;text-underline-offset:4px}li{padding-left:4px;margin:10px 0}pre{overflow:auto;background:#f1f4fa;border-radius:14px;padding:20px;font-size:12px;line-height:1.7}code{font-family:Consolas,monospace}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #e4e9f1;text-align:left;padding:12px 14px;vertical-align:top}th{background:#f0f4fc;font-weight:750}footer{padding:20px;color:#7c8799;font-size:12px;text-align:center}@media(max-width:650px){main{margin:16px 12px;padding:28px 20px}h1{font-size:27px}h2{font-size:20px}p,li{font-size:14px}}@media print{body{background:white}main{border:0;margin:0;padding:0}h2{break-after:avoid}a{color:inherit}}'''
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>홍익이 · 팀원 사용 안내</title><style>'+css+'</style><header>HONGIK DRIVE · TEAM GUIDE · 2026.11.22</header><main>'+''.join(blocks)+'</main><footer>CARLA 실험 운영 / NuRec 개발 옵션 · 참가자 데이터는 별도 비공개 보관</footer></html>'

def build(output,bundle,bootstrap):
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():
        raise RuntimeError('Commit reviewed source before creating a release')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    output,bundle=Path(output).resolve(),Path(bundle).resolve()
    if output==ROOT or ROOT in output.parents:raise ValueError('Use an output folder outside the source checkout')
    output.mkdir(parents=True,exist_ok=True);release=output/NAME
    release.mkdir(exist_ok=False);payload=release/'files';payload.mkdir()
    def put(name,data):
        if not approved(name):raise ValueError('Unapproved output path: '+name)
        target=payload/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    # Reuse only already-delivered optional dependencies, motion helpers and
    # static UI assets; current Git source replaces all older source below.
    with zipfile.ZipFile(bootstrap) as archive:
        for entry in archive.infolist():
            parts=entry.filename.split('/files/',1)
            if len(parts)!=2 or entry.is_dir():continue
            name=parts[1]
            if not approved(name) or name.startswith('cache/'):continue
            data=archive.read(entry)
            if name.startswith('live/') and allowed(name[5:]):check_content(name[5:],data)
            put(name,data)
    names=[n for n in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0') if n]
    for name in names:
        if not allowed(name):raise ValueError('Unapproved Git source: '+name)
        data=source_bytes(ROOT/name);check_content(name,data);put('live/'+name,data)
        if name.startswith('data-server-py/'):put(name,data)
    for folder in AUDIO:
        source=bundle/'cache'/folder
        if not source.is_dir():raise FileNotFoundError('Missing audio folder: '+folder)
        for path in source.iterdir():
            if not path.is_file() or re.search(r'backup|before|previous|\.part',path.name,re.I):continue
            name='cache/'+folder+'/'+path.name
            if approved(name):put(name,path.read_bytes())
    # Refresh static mobile assets which intentionally stay outside public Git.
    for folder in ('mobile','ui_assets'):
        for path in (bundle/'live'/folder).glob('*'):
            name='live/'+folder+'/'+path.name
            if path.is_file() and approved(name) and not (ROOT/folder/path.name).is_file():put(name,path.read_bytes())
    for name in ('apply_team_update.py','repo_safety.py','APPLY_TEAM_UPDATE.bat'):
        shutil.copy2(ROOT/name,release/name)
    shutil.copy2(ROOT/'TEAM_START_HERE.html',release/'00_팀원_사용안내.html')
    shutil.copy2(ROOT/'docs/TEAM-START-HERE-KO.md',release/'00_팀원_사용안내.md')
    manifest=dict(schema=1,date='2026-11-22',source_commit=revision,branch='codex/portable-motion-20261111',
                  requires_existing_bundle=True,excludes=['participant data','credentials','music','NuRec models','WSL VHD'],files=[])
    for path in sorted(payload.rglob('*')):
        if path.is_file():manifest['files'].append(dict(path=path.relative_to(payload).as_posix(),size=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (release/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    from apply_team_update import apply
    apply(bundle,check=True,package=release)
    archive=output/(NAME+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(release.rglob('*')):
            if path.is_file():z.write(path,NAME+'/'+path.relative_to(release).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise RuntimeError('ZIP integrity check failed')
    result=dict(file=str(archive),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),source_commit=revision,files=len(manifest['files']))
    (output/'RELEASE-CHECKSUMS.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--guide-only',action='store_true')
    parser.add_argument('--output',type=Path);parser.add_argument('--bundle',type=Path);parser.add_argument('--bootstrap',type=Path)
    args=parser.parse_args()
    if args.guide_only:
        target=ROOT/'TEAM_START_HERE.html'
        if target.exists():
            import tempfile,uuid
            shutil.copy2(target,Path(tempfile.gettempdir())/('hongik-team-guide-'+uuid.uuid4().hex+'.html'))
        target.write_text(guide_html(),encoding='utf-8');print(target)
    elif all((args.output,args.bundle,args.bootstrap)):print(json.dumps(build(args.output,args.bundle,args.bootstrap),indent=2))
    else:parser.error('Provide --guide-only or --output, --bundle and --bootstrap')
