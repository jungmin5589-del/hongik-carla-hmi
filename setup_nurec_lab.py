"""Restore the existing licensed SSD runtime on another lab PC; motion stays off."""
import argparse,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path
from nurec_paths import data_root,official_root
from nurec_environment import python_path,carla_root,distro_name,distributions,vhd_path,save

ROOT=Path(__file__).resolve().parent
IMAGE=json.loads((ROOT/'settings/runtime-lock.json').read_text('utf-8'))['nurec']['image']
NO_WINDOW=0x08000000 if os.name=='nt' else 0
PROBE="import json,importlib.metadata as m;import carla,numpy,scipy,PIL,pygame,grpc,google.protobuf,cv2;print(json.dumps({p:m.version(p) for p in ['carla','numpy','scipy','Pillow','pygame','grpcio','protobuf','opencv-python-headless']}))"

def run(command,timeout=30):
    result=subprocess.run([str(p) for p in command],capture_output=True,timeout=timeout,creationflags=NO_WINDOW)
    def decode(data):
        return data.decode('utf-16',errors='replace') if data.startswith((b'\xff\xfe',b'\xfe\xff')) else data.decode('utf-16-le' if b'\0' in data[:160] else 'utf-8',errors='replace')
    result.stdout=decode(result.stdout);result.stderr=decode(result.stderr);return result

def probe_python(python):
    result=run([python,'-c',PROBE],20)
    if result.returncode:raise RuntimeError('NuRec Python 의존성이 부족해요: '+result.stderr[-800:])
    # Pygame may print its greeting before the final JSON object.
    data=json.loads(result.stdout.strip().splitlines()[-1])
    if data['carla']!='0.9.16':raise RuntimeError('CARLA 0.9.16 클라이언트가 필요해요.')
    return data

def prepare_python(root,portable=False):
    try:
        python=root/'python/python.exe' if portable else python_path(True)
        probe_python(python);return python
    except (OSError,RuntimeError,subprocess.SubprocessError,ValueError):pass
    from render_options import native_live
    source=native_live().parent/'python';target=root/'python'
    marker=target/'.hongik-nurec-python'
    if target.exists() and not marker.is_file():raise RuntimeError('기존 python 폴더는 덮어쓰지 않았어요. NuRec 전용 새 폴더가 필요해요.')
    if shutil.disk_usage(root).free<2*1024**3:raise RuntimeError('Python 준비에 SSD 여유 공간 2GiB 이상이 필요해요.')
    target.mkdir(exist_ok=True);marker.write_text('Owned isolated portable NuRec Python',encoding='ascii')
    print('NuRec 전용 Python을 별도 폴더에 준비하고 있어요.',file=sys.stderr,flush=True)
    shutil.copytree(source,target,dirs_exist_ok=True)
    python=target/'python.exe'
    print('고정된 NuRec 패키지를 확인·설치하고 있어요.',file=sys.stderr,flush=True)
    result=run([python,'-m','pip','install','--disable-pip-version-check','--no-input','-r',ROOT/'settings/requirements.lock.txt'],900)
    if result.returncode:raise RuntimeError('NuRec 전용 Python 설치 실패: '+result.stderr[-1500:])
    probe_python(python);return python

def prepare_distribution(root):
    try:return distro_name(True)
    except FileNotFoundError:pass
    vhd=vhd_path(root)
    if not vhd.is_file():raise FileNotFoundError('SSD의 WSL/NuRec22/ext4.vhdx가 필요해요. 원본 환경을 먼저 복구해 주세요.')
    name='Hongik-NuRec22'
    if name in {r['name'] for r in distributions()}:raise RuntimeError('Hongik-NuRec22 이름이 다른 환경에 사용 중이에요. 기존 환경을 변경하지 않았어요.')
    # Use the supplied existing ext4 VHD. No unregister, conversion, or deletion
    # of the lab's unrelated distributions, and no automatic Windows restart.
    print('SSD의 기존 NuRec WSL 환경을 이 PC에 등록하고 있어요.',file=sys.stderr,flush=True)
    result=run(['wsl.exe','--import-in-place',name,vhd],90)
    if result.returncode:raise RuntimeError('WSL 등록 실패. Windows의 WSL2 설치/재시작이 필요한지 확인해 주세요: '+result.stderr[-800:])
    return name

def inspect(prepare=False,portable=False):
    report=dict(errors=[],notes=[],motion_enabled=False,actual_render_verified=False,physical_lab_verified=False)
    try:
        root=data_root();report['source_root']=str(root);integration=official_root()
        if prepare:
            # Retain the licensed source archive, but carry the small MIT
            # coordinate helper locally rather than a complete Unreal checkout.
            bundled=root/'source/official-integration';bundled.mkdir(exist_ok=True)
            helper=bundled/'projection_functions.py'
            if not helper.exists():shutil.copy2(integration/'projection_functions.py',helper)
            python=prepare_python(root,portable);distro=prepare_distribution(root);engine=carla_root(True)
            save(dict(python=str(python),carla_root=str(engine),distro=distro))
            from deploy_nurec_option import deploy,NUREC
            deploy(root/'live',NUREC)
        else:python=python_path(True);distro=distro_name(True);engine=carla_root(True)
        report.update(python=str(python),packages=probe_python(python),distro=distro,carla_root=str(engine))
        check=run(['wsl.exe','-d',distro,'-u','root','--exec','bash','-lc','timeout 20 docker info --format "{{.ServerVersion}}"'],30)
        if check.returncode:raise RuntimeError('NuRec WSL 안의 Docker 서비스가 준비되지 않았어요: '+check.stderr[-700:])
        report['docker']=check.stdout.strip()
        check=run(['wsl.exe','-d',distro,'-u','root','--exec','docker','image','inspect',IMAGE,'--format','{{.Id}}'],20)
        if check.returncode:raise RuntimeError('고정된 NuRec 컨테이너 이미지가 없어요. SSD의 기존 WSL 환경 또는 해당 이미지 복구가 필요해요.')
        report['pinned_image_present']=True
        check=run(['wsl.exe','-d',distro,'-u','root','--exec','docker','run','--rm','--gpus','all','--entrypoint','nvidia-smi',IMAGE,'--query-gpu=name,memory.total','--format=csv,noheader'],40)
        if check.returncode:raise RuntimeError('Docker 컨테이너의 NVIDIA GPU 연결을 확인하지 못했어요: '+check.stderr[-700:])
        report['container_gpu']=check.stdout.strip()
        check=run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],10)
        if check.returncode:raise RuntimeError('Windows NVIDIA GPU 드라이버를 확인해 주세요.')
        report['gpu']=check.stdout.strip()
        report['notes'].append('설치 점검 통과는 3면 30fps·자연스러운 차량·6축 모션 검증을 의미하지 않아요.')
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:report['errors'].append(str(exc))
    report['environment_ready']=not report['errors']
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--portable-python',action='store_true');parser.add_argument('--json',action='store_true');args=parser.parse_args()
    report=inspect(args.prepare,args.portable_python)
    folder=ROOT/'setup-runs';folder.mkdir(exist_ok=True)
    path=folder/('nurec-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not args.json:print('\n준비 후 65_START_NUREC_LAB.bat에서 상황을 선택하세요.\n점검 기록: '+str(path))
    if not report['environment_ready']:raise SystemExit(1)

if __name__=='__main__':main()
