"""Explicitly stop this NuRec runtime and release its SSD-backed WSL VHD."""
import subprocess
from pathlib import Path
from nurec_environment import distro_name,python_path,distributions,vhd_path
from nurec_paths import data_root
from render_options import drive_state,post,stop_nurec

def main():
    live=data_root()/'live';state=drive_state()
    if state and state.get('kind')!='hongik-nurec':raise RuntimeError('현재 CARLA 버전은 그대로 두었어요. NuRec 종료 파일이에요.')
    if state:
        post('/control',dict(mode='paused',session_id=state['scenario']['session']))
        stop_nurec(live,python_path(True))
    distro=distro_name(True)
    matched=next((item for item in distributions() if item['name']==distro),None)
    if not matched or Path(matched['vhd']).resolve()!=vhd_path().resolve():
        raise RuntimeError('NuRec 주행은 종료했지만 다른 작업이 있을 수 있는 WSL은 종료하지 않았어요. SSD 연결 상태를 직접 확인해 주세요.')
    # Only the distribution matched to this existing NuRec VHD is selected.
    # Do not use global wsl --shutdown or stop the lab's unrelated distributions.
    subprocess.run(['wsl.exe','--terminate',distro],check=True,creationflags=0x08000000,timeout=45)
    print('NuRec과 전용 WSL 환경을 종료했어요. Windows의 하드웨어 안전 제거로 SSD를 분리하세요.')

if __name__=='__main__':main()
