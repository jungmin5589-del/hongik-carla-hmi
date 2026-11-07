"""Prepare a local carry-to-lab folder. Never uploads engines, audio or credentials."""
import argparse,hashlib,json,os,shutil,subprocess,sys,urllib.request,uuid,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PACKAGES=['carla==0.9.16','numpy==2.2.6','scipy==1.15.3','pygame==2.6.1','Pillow==12.0.0','requests==2.32.5','qrcode==8.2','cryptography==46.0.3','aiohttp==3.13.2','pywebpush==2.0.3','py-vapid==1.9.2','http-ece==1.2.1','pip==25.3']
MOBILE=['app.css','app.js','connect.html','icon-192.png','icon-512.png','icon.svg','index.html','manifest.webmanifest','sw.js']

def copy_source(destination):
    from repo_safety import allowed,check_content
    backup=destination/'previous-source'/uuid.uuid4().hex
    files=[n for n in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if n]
    manifest=[]
    for name in files:
        if not allowed(name):raise RuntimeError('Not approved source: '+name)
        source=ROOT/name;data=source.read_bytes();check_content(name,data);target=destination/'live'/name
        if target.exists() and target.read_bytes()!=data:
            old=backup/name;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,old)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        manifest.append(dict(path='live/'+name,sha256=hashlib.sha256(data).hexdigest()))
    for name in MOBILE:shutil.copy2(ROOT/'mobile'/name,destination/'live/mobile'/name)
    (destination/'live/ui_assets').mkdir(exist_ok=True)
    for p in (ROOT/'ui_assets').glob('552-*.svg'):shutil.copy2(p,destination/'live/ui_assets'/p.name)
    (destination/'SOURCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--refresh-source-only',action='store_true');args=parser.parse_args()
    target=args.destination.resolve()
    if target==ROOT or ROOT in target.parents or target in ROOT.parents:raise RuntimeError('Use a separate carry-to-lab folder')
    target.mkdir(parents=True,exist_ok=True);(target/'live').mkdir(exist_ok=True)
    copy_source(target)
    if args.refresh_source_only:print('Refreshed source only: '+str(target));return
    # A single archive avoids thousands of slow metadata writes to a USB disk.
    # It is extracted on the lab's internal SSD, beside the old installation.
    engine=Path('C:/CARLA_0.9.16');archive=target/'CARLA_0.9.16.zip'
    if not archive.is_file():
        temporary=archive.with_suffix('.building.zip');count=0
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
            for name in ('CarlaUE4.exe','LICENSE','README','CHANGELOG'):z.write(engine/name,name)
            for folder in ('CarlaUE4','Engine'):
                for source in (engine/folder).rglob('*'):
                    if not source.is_file() or source.suffix=='.pdb' or any(p in ('Saved','DerivedDataCache','Intermediate') for p in source.relative_to(engine).parts):continue
                    z.write(source,source.relative_to(engine).as_posix());count+=1
                    if count%3000==0:print('Archived '+str(count)+' engine files',flush=True)
        with zipfile.ZipFile(temporary) as z:
            if z.testzip():raise RuntimeError('Engine archive integrity failure')
        os.replace(temporary,archive)
        print('Engine archive verified',flush=True)
    for name in ('city-audio','english-audio','sohee-narration','sohee-pedestrian','exterior-gait','recorded-cabin','mechanical-recording','recorded-footsteps'):
        shutil.copytree(ROOT.parent/'cache'/name,target/'cache'/name,dirs_exist_ok=True)
    from passenger_music import MUSIC,TRACKS
    music=target/'cache/music';music.mkdir(exist_ok=True)
    for item in TRACKS:shutil.copy2(MUSIC/item[4],music/item[4])
    python=target/'python';python.mkdir(exist_ok=True)
    archive=ROOT.parent/'cache/python-3.12.10-embed-amd64.zip'
    if not archive.is_file():urllib.request.urlretrieve('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',archive)
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise RuntimeError('Invalid Python runtime archive')
        z.extractall(python)
    # Explicit paths suffice for these wheels; importing site would also add
    # the host user's unrelated Roaming/Python packages on Windows.
    (python/'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n../live\n',encoding='utf-8')
    site=python/'Lib/site-packages';wheels=ROOT.parent/'lab-wheelhouse-py312'
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--find-links',str(wheels),'--target',str(site),*PACKAGES],check=True)
    subprocess.run([str(python/'python.exe'),'-m','pip','check'],check=True)
    (target/'00_START_HERE.md').write_text((ROOT/'docs/LAB-READY-KO.md').read_text(encoding='utf-8'),encoding='utf-8')
    print('Local portable bundle prepared: '+str(target),flush=True)

if __name__=='__main__':main()
