"""Deploy only reviewed application files; never copy licensed data or secrets."""
import argparse
import hashlib
from pathlib import Path
import shutil
import time
import uuid

ROOT=Path(__file__).resolve().parent

def source_bytes(path):
    data=path.read_bytes()
    return data.replace(b'\r\n',b'\n') if path.suffix=='.sh' else data
SHARED=('render_options.py','render_options.html','deploy_nurec_option.py','65_START_NUREC_LAB.bat',
    'nurec_environment.py','setup_nurec_lab.py','66_NUREC_SETUP.bat',
    'stop_nurec_lab.py','67_STOP_NUREC_LAB.bat',
    'nurec_paths.py','lab_viewer.py','launch_lab.py','runtime_version.py','experiment.html','research_voice.py')
NUREC=tuple(dict.fromkeys(SHARED+('launch_nurec_lab.py','nurec_surround.py','nurec_natural.py','nurec_navigation.py',
    'scene_bridge.py','launch_live.py','switch_profile.py','profile_sources.py','asset_editing.py','serve-live.sh',
    'settings/runtime-lock.json','settings/requirements.lock.txt',
    'lab_capture.py','lab_settings.py','frame_validation.py','traffic_intro.py',
    'navigation.js','navigation_adapter.py','navigation_boot.js','midterm_panel.js','midterm_panel.css',
    'feedback_voice.js','highway_blockade.py','night_weaving.py','language.js','scene_audio.js',
    'city_study.js','city_study.css','exterior_sound.js','underbody_sound.js','driving_sound.js',
    'driving_sound.css','recorded_cabin.js','course_ui/index.html','course_ui/cockpit.js','course_ui/cockpit.css',
    'course_ui/vendor/PretendardVariable.woff2','course_ui/vendor/Pretendard-LICENSE.txt')))

def changes(target,names):
    target=Path(target).resolve()
    if not target.is_dir():raise FileNotFoundError('Existing live folder required')
    result=[]
    for name in names:
        source=(ROOT/name).resolve();destination=(target/name).resolve()
        if not destination.is_relative_to(target):raise ValueError('Destination escaped the live folder')
        if not source.is_file():raise FileNotFoundError('Missing application source: '+name)
        if source==destination:continue
        if destination.is_file() and hashlib.sha256(source_bytes(source)).digest()==hashlib.sha256(destination.read_bytes()).digest():continue
        result.append((source,destination,name))
    return result

def deploy(target,names,dry_run=False):
    target=Path(target).resolve();pending=changes(target,names)
    if dry_run:return len(pending)
    backup=target/'backups'/('nurec-option-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    # Back up the complete change set before mutating the first target file.
    for source,destination,name in pending:
        if destination.is_file():
            saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,saved)
    for source,destination,name in pending:
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.installing')
        temporary.write_bytes(source_bytes(source));temporary.replace(destination)
    return len(pending)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    from nurec_paths import data_root
    from render_options import native_live
    targets=[(data_root()/'live',NUREC)]
    try:
        native=native_live()
        if native!=targets[0][0]:targets.append((native,NUREC))
    except FileNotFoundError:pass
    for target,names in targets:
        count=deploy(target,names,args.check)
        print(('Would update ' if args.check else 'Updated ')+str(count)+' application files: '+str(target))

if __name__=='__main__':main()
