"""Apply a reviewed team release; preserve local settings and research records."""
import argparse
import hashlib
import json
import shutil
import socket
import sys
import uuid
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))  # Portable Python's _pth excludes the script folder.
AUDIO={'city-audio','english-audio','exterior-gait','mechanical-recording',
       'recorded-cabin','recorded-footsteps','research-voice','sohee-narration','sohee-pedestrian'}
PRIVATE={'mobile-data','native-runs','.git','lab.local.json','drive-config.json',
         'research.sqlite3','research-data','subscriptions.json'}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def approved(name):
    rel=PurePosixPath(name)
    if not name or '\\' in name or ':' in name or rel.is_absolute() or '..' in rel.parts:return False
    if PRIVATE.intersection(rel.parts):return False
    if rel.suffix.lower() in {'.pem','.key','.crt','.cer','.sqlite','.sqlite3','.db','.part'}:return False
    if rel.parts[0]=='live':
        # This list is part of the audited public source, not supplied by a ZIP.
        from repo_safety import allowed
        inner=rel.relative_to('live').as_posix()
        return allowed(inner) or (len(rel.parts)==3 and rel.parts[1]=='mobile' and rel.name in
            {'app.css','connect.html','icon-192.png','icon-512.png','icon.svg','manifest.webmanifest','sw.js'}) or (
            len(rel.parts)==3 and rel.parts[1]=='ui_assets' and rel.name.startswith('552-') and rel.suffix=='.svg')
    if rel.parts[0]=='cache':
        return len(rel.parts)==3 and rel.parts[1] in AUDIO and rel.suffix.lower() in {'.wav','.mp3','.ogg','.json','.md','.txt'}
    if rel.parts[0]=='data-server-py':
        return rel.suffix=='.py' or rel.as_posix()=='data-server-py/sixdof_rs.pyd'
    if rel.parts[0]=='python':
        return rel.parts[:3]==('python','Lib','site-packages') and (
            len(rel.parts)>3 and (rel.parts[3] in {'serial','websockets'} or
            rel.parts[3].startswith(('pyserial-','websockets-'))))
    return len(rel.parts)==1 and rel.name in {'START_LAPTOP.bat','START_MOTION_PROFILE.bat'}

def apply(target,check=False,package=ROOT):
    target,package=Path(target).resolve(),Path(package).resolve()
    if not (target/'live/native_carla.py').is_file() or not (target/'python/python.exe').is_file():
        raise ValueError('Select the complete existing Hongik-CARLA-Lab-20261107 folder')
    if package==target or target in package.parents or package in target.parents:
        raise ValueError('Extract the update into a separate folder outside the installed app')
    manifest=json.loads((package/'manifest.json').read_text('utf-8'))
    pending=[];seen=set();payload=(package/'files').resolve()
    for item in manifest['files']:
        name=item['path']
        if name in seen or not approved(name):raise ValueError('Unapproved or duplicate package path: '+name)
        seen.add(name);source=(payload/name).resolve();destination=(target/name).resolve()
        if not source.is_relative_to(payload) or not destination.is_relative_to(target):raise ValueError('Escaped package path')
        if digest(source)!=item['sha256']:raise ValueError('Package checksum mismatch: '+name)
        if digest(destination)!=item['sha256']:pending.append((source,destination,name))
    if check:return dict(checked=True,files=len(seen),changed=len(pending),source_commit=manifest['source_commit'])
    for port in (2016,2026,8774,8765,8766):
        with socket.socket() as connection:
            connection.settimeout(.2)
            if connection.connect_ex(('127.0.0.1',port))==0:
                raise RuntimeError('Close the driving app normally before updating (port '+str(port)+')')
    backup=target/'update-backups'/('team-20261122-'+uuid.uuid4().hex)
    # Back up the entire change set before replacing the first application file.
    for source,destination,name in pending:
        if destination.is_file():
            saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,saved)
    for source,destination,name in pending:
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.installing')
        shutil.copy2(source,temporary);temporary.replace(destination)
    if not all(digest(target/item['path'])==item['sha256'] for item in manifest['files']):
        raise RuntimeError('Installed checksum mismatch; originals remain in update-backups')
    report=dict(applied=True,files=len(seen),changed=len(pending),source_commit=manifest['source_commit'],
                backup=str(backup),local_configuration_preserved=True)
    backup.mkdir(parents=True,exist_ok=True)
    (backup/'installation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (target/'TEAM-UPDATE-20261122.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--target-bundle',type=Path,required=True)
    parser.add_argument('--check',action='store_true');args=parser.parse_args()
    print(json.dumps(apply(args.target_bundle,args.check),ensure_ascii=False,indent=2))
