"""Offline-only 1.7B emotion-controlled exterior acting. Never used by driving runtime."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
from city_voice import CACHE
from exterior_dialogue import DIALOGUE,VOICE_ENGINE,VOICE_INSTRUCTION
from prepare_city_audio import COURSE

MODEL=Path(__file__).resolve().parents[1]/'cache/models/qwen3-tts-1.7b-customvoice'
REVISION='0c0e3051f131929182e2c023b9537f8b1c68adfe'

def main():
 if '--download' in sys.argv:
  os.environ.setdefault('HF_HUB_DISABLE_XET','1')
  os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','60')
  from huggingface_hub import snapshot_download
  snapshot_download('Qwen/'+VOICE_ENGINE,revision=REVISION,local_dir=MODEL,token=False,
                    allow_patterns=['*.json','*.safetensors','*.txt','*.model','*.tiktoken'],max_workers=4)
  return
 if '--worker' not in sys.argv:
  from launch_live import memory_state
  if memory_state()<6:raise RuntimeError('Offline acting preparation needs 6 GiB commit headroom')
  subprocess.run([str(COURSE/'.tts-env/Scripts/python.exe'),'-u',str(Path(__file__).resolve()),'--worker'],check=True,
                 env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1'),creationflags=0x08000000)
  return
 import torch,soundfile as sf
 from qwen_tts import Qwen3TTSModel
 if not (MODEL/'model.safetensors').is_file():raise RuntimeError('Download official weights first with --download in the TTS environment')
 if not torch.cuda.is_available() or torch.cuda.mem_get_info()[0]<4.5*1024**3:raise RuntimeError('Stop driving first; offline acting needs 4.5 GiB free GPU memory')
 torch.set_num_threads(2);CACHE.mkdir(parents=True,exist_ok=True)
 manifest=CACHE/'manifest.json';entries=json.loads(manifest.read_text(encoding='utf-8'))['entries']
 model=None
 for _,key,text in DIALOGUE:
  identity='\n'.join((VOICE_ENGINE,REVISION,VOICE_INSTRUCTION,'Aiden',text))
  filename=hashlib.sha256(identity.encode()).hexdigest()+'.wav';target=CACHE/filename
  if target.exists():
   try:
    info=sf.info(str(target))
    if info.frames<=0 or info.channels!=1 or info.samplerate!=24000:raise ValueError('Invalid existing waveform')
   except (RuntimeError,ValueError):target.rename(target.with_suffix('.invalid-'+uuid.uuid4().hex+'.wav'))
  if not target.exists():
   if model is None:model=Qwen3TTSModel.from_pretrained(str(MODEL),device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa')
   print('Synthesizing aggressive exterior line: '+key,flush=True)
   with torch.inference_mode():
    torch.manual_seed(184)
    wavs,sr=model.generate_custom_voice(text=text,language='Korean',speaker='Aiden',instruct=VOICE_INSTRUCTION,
                                      max_new_tokens=min(1024,len(text)*12+120),do_sample=True)
   temporary=target.with_suffix('.tmp.wav');sf.write(str(temporary),wavs[0],sr,subtype='PCM_16');os.replace(temporary,target)
  info=sf.info(str(target))
  if info.frames<=0 or info.channels!=1 or info.samplerate!=24000:raise RuntimeError('Invalid generated exterior waveform')
  entries[key]=dict(filename=filename,text=text,speaker='Aiden',engine=VOICE_ENGINE,instruct=VOICE_INSTRUCTION,
                    model_revision=REVISION,duration_s=info.duration,sample_rate=info.samplerate,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
  shutil.copy2(manifest,CACHE/('manifest-before-acting-'+uuid.uuid4().hex+'.json'))
  temporary=manifest.with_suffix('.tmp.json');temporary.write_text(json.dumps(dict(entries=entries),ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temporary,manifest)
  print('Prepared aggressive exterior line: '+key,flush=True)

if __name__=='__main__':main()
