"""Apply source updates only when the installed baseline matches. Preserve lab edits."""
import argparse,hashlib,json,shutil,socket,uuid
from pathlib import Path,PurePosixPath

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
def apply(package,target):
    package=package.resolve();target=target.resolve()
    if not target.is_dir():raise ValueError('Select the existing live folder')
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'));plan=[];conflicts=[]
    for item in manifest['files']:
        rel=PurePosixPath(item['path'])
        if rel.is_absolute() or '..' in rel.parts or '\\' in item['path'] or rel.parts[0] in ('.git','cache','mobile-data'):
            raise ValueError('Invalid update path')
        dest=(target/str(rel)).resolve();source=(package/'files'/str(rel)).resolve()
        if not dest.is_relative_to(target) or not source.is_relative_to(package/'files'):raise ValueError('Update path escapes its folder')
        if digest(source)!=item['sha256']:raise ValueError('Damaged update file: '+str(rel))
        current=digest(dest)
        if current==item['sha256']:continue
        if current!=item['previous_sha256'] or (dest.exists() and not dest.is_file()):conflicts.append(str(rel))
        plan.append((source,dest,rel))
    if conflicts:return dict(applied=False,conflicts=conflicts,message='Lab-modified files were preserved. No source files were replaced.')
    backup=target.parent/'update-backups'/uuid.uuid4().hex
    for source,dest,rel in plan:
        if dest.is_file():
            old=backup/str(rel);old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,old)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    return dict(applied=True,updated=len(plan),backup=str(backup),version=manifest['version'])
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True);parser.add_argument('--target-live',type=Path,required=True);args=parser.parse_args()
    with socket.socket() as probe:
        probe.settimeout(.3)
        if probe.connect_ex(('127.0.0.1',8774))==0:raise RuntimeError('Close the running driving app normally before applying this update')
    result=apply(args.package,args.target_live);print(json.dumps(result,ensure_ascii=True,indent=2))
    if not result['applied']:raise SystemExit(2)
if __name__=='__main__':main()
