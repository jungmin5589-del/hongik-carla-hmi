"""Per-PC runtime paths. No credentials or licensed data are written to Git."""
import json,os,shutil,time,uuid
from pathlib import Path
from nurec_paths import data_root

CODE=Path(__file__).resolve().parent
CONFIG=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local')))/'HongikDrive/nurec-setup.json'

def config():
    try:return json.loads(CONFIG.read_text('utf-8'))
    except FileNotFoundError:return {}

def save(values):
    CONFIG.parent.mkdir(parents=True,exist_ok=True)
    if CONFIG.exists():shutil.copy2(CONFIG,CONFIG.with_name('nurec-setup.'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex+'.backup'))
    temporary=CONFIG.with_name('nurec-setup.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(dict(config(),**values),ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(CONFIG)

def python_path(required=False):
    values=[os.environ.get('HONGIK_NUREC_PYTHON'),config().get('python')]
    try:values.append(data_root()/'python/python.exe')
    except FileNotFoundError:pass
    values.append(r'C:\CARLA_0.9.16\diagnostics\nurec-env\Scripts\python.exe')
    for value in values:
        if value and Path(value).is_file():return Path(value).resolve()
    if required:raise FileNotFoundError('NuRec Python이 없어요. 66_NUREC_SETUP.bat를 먼저 실행해 주세요.')
    return Path(values[-1])

def carla_root(required=False):
    values=[os.environ.get('HONGIK_NUREC_CARLA_ROOT'),config().get('carla_root'),r'C:\CARLA_0.9.16',CODE.parent/'CARLA_0.9.16']
    try:values.append(Path(data_root().anchor)/'Hongik-CARLA-Lab-20261107/CARLA_0.9.16')
    except FileNotFoundError:pass
    for value in values:
        if value and (Path(value)/'CarlaUE4.exe').is_file():return Path(value).resolve()
    if required:raise FileNotFoundError('별도 CARLA 0.9.16 엔진이 필요해요. 66_NUREC_SETUP.bat에서 확인해 주세요.')
    return Path(r'C:\CARLA_0.9.16')

def distributions():
    if os.name!='nt':return []
    import winreg
    result=[]
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Lxss') as parent:
            for i in range(winreg.QueryInfoKey(parent)[0]):
                with winreg.OpenKey(parent,winreg.EnumKey(parent,i)) as key:
                    name=winreg.QueryValueEx(key,'DistributionName')[0];base=winreg.QueryValueEx(key,'BasePath')[0]
                    result.append(dict(name=name,vhd=str(Path(base.removeprefix('\\\\?\\'))/'ext4.vhdx')))
    except FileNotFoundError:pass
    return result

def vhd_path(root=None):return Path((root or data_root()).anchor)/'WSL/NuRec22/ext4.vhdx'

def distro_name(required=False):
    records=distributions();names={record['name'] for record in records}
    explicit=os.environ.get('HONGIK_NUREC_DISTRO')
    if explicit:
        if explicit in names:return explicit
        raise FileNotFoundError('지정한 NuRec WSL 배포판이 등록되지 않았어요.')
    try:
        target=vhd_path().resolve()
        for record in records:
            if Path(record['vhd']).resolve()==target:return record['name']
    except FileNotFoundError:pass
    if required:raise FileNotFoundError('이 PC에 NuRec WSL 환경을 등록해야 해요. 66_NUREC_SETUP.bat를 실행해 주세요.')
    return 'Ubuntu-22.04'
