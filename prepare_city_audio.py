"""One-time offline synthesis; audio and models never enter Git."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from city_voice import CACHE,TEXTS
from exterior_dialogue import DIALOGUE

COURSE=Path.home()/'Desktop/홍익대/2026 2학기/휴먼 자율주행 인터렉션 디자인/CARLA-YOLO-실습'
MODEL=COURSE/'models/qwen3-tts-0.6b-sohee'

def main():
 if '--worker' not in sys.argv:
  from launch_live import memory_state
  if memory_state()<4:raise RuntimeError('Voice preparation requires 4 GiB commit headroom')
  subprocess.run([str(COURSE/'.tts-env/Scripts/python.exe'),'-u',str(Path(__file__).resolve()),'--worker'],check=True,
                 env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1'),creationflags=0x08000000)
  return
 import torch,soundfile as sf
 from qwen_tts import Qwen3TTSModel
 torch.set_num_threads(2)
 if not torch.cuda.is_available() or torch.cuda.mem_get_info()[0]<2.8*1024**3:raise RuntimeError('Not enough free GPU memory for one-time audio preparation')
 CACHE.mkdir(parents=True,exist_ok=True);manifest=CACHE/'manifest.json'
 entries=json.loads(manifest.read_text(encoding='utf-8'))['entries'] if manifest.exists() else {}
 model=None
 for key,(text,speaker) in TEXTS.items():
  if key in {item[1] for item in DIALOGUE}:continue  # Styled external acting uses prepare_exterior_voice.py.
  filename=hashlib.sha256((speaker+'\n'+text).encode()).hexdigest()+'.wav';target=CACHE/filename
  if not target.exists():
   if model is None:model=Qwen3TTSModel.from_pretrained(str(MODEL),device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa')
   with torch.inference_mode():
    torch.manual_seed(184)
    wavs,sr=model.generate_custom_voice(text=text,language='Korean',speaker=speaker,max_new_tokens=min(1536,len(text)*8+100),do_sample=True)
   temporary=target.with_suffix('.tmp.wav');sf.write(str(temporary),wavs[0],sr,subtype='PCM_16');os.replace(temporary,target)
  entries[key]=dict(filename=filename,text=text,speaker=speaker,engine='Qwen3-TTS-12Hz-0.6B-CustomVoice',sha256=hashlib.sha256(target.read_bytes()).hexdigest())
  if manifest.exists():
   import shutil
   shutil.copy2(manifest,CACHE/('manifest-before-'+time.strftime('%Y%m%d-%H%M%S')+'-'+key+'.json'))
  manifest.write_text(json.dumps(dict(entries=entries),ensure_ascii=False,indent=2),encoding='utf-8')
  print('Prepared city audio: '+key,flush=True)

if __name__=='__main__':main()
