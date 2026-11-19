"""Start the existing calibrated CARLA app with motion OFF and open study setup."""
import json,sys,time,urllib.request,webbrowser
from pathlib import Path

def main():
 from lab_viewer import monitors,surround_rect
 from launch_lab import main as launch
 sys.argv=[sys.argv[0],'--welcome','--no-browser']+([] if surround_rect(monitors()) else ['--preview'])
 launch()
 try:
  r=urllib.request.Request('http://127.0.0.1:8774/api/stt/start',data=b'{}',headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(r,timeout=5) as f:status=json.load(f)
  print('STT:',status.get('state','not installed'))
 except (OSError,ValueError):print('Prepare local STT from the study page when parked. Text input remains available.')
 webbrowser.open('http://127.0.0.1:8774/experiment')
if __name__=='__main__':main()
