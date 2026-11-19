"""Install an isolated CPU recognizer; never changes the CARLA Python environment."""
import os,subprocess,sys,venv
from pathlib import Path
PACKAGES=('faster-whisper==1.2.1','av==16.1.0','ctranslate2==4.9.0')
def main():
 if sys.version_info[:2]!=(3,12):raise RuntimeError('Use system Python 3.12 for local STT setup.')
 root=Path(os.environ['LOCALAPPDATA'])/'HongikSTT/venv'
 if not (root/'Scripts/python.exe').exists():venv.EnvBuilder(with_pip=True).create(root)
 subprocess.run([str(root/'Scripts/python.exe'),'-m','pip','install',*PACKAGES],check=True)
 print('Local CPU STT installed. Open /experiment and prepare the model before driving.')
if __name__=='__main__':main()
