"""One-time local multilingual synthesis, guarded and resumable."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from research_voice import CACHE,ENGINE,entries
from prepare_city_audio import COURSE,MODEL

def main():
 if '--worker' not in sys.argv:
  from launch_live import memory_state
  if memory_state()<6:raise RuntimeError('Voice preparation requires 6 GiB commit headroom')
  subprocess.run([str(COURSE/'.tts-env/Scripts/python.exe'),'-u',str(Path(__file__).resolve()),'--worker'],check=True,
    env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2'),creationflags=0x08000000)
  return
 import torch,soundfile as sf
 from qwen_tts import Qwen3TTSModel
 if not torch.cuda.is_available() or torch.cuda.mem_get_info()[0]<4.5*1024**3:raise RuntimeError('Stop driving first; synthesis needs 4.5 GiB free GPU memory')
 torch.set_num_threads(2);CACHE.mkdir(parents=True,exist_ok=True);manifest=CACHE/'manifest.json'
 saved=json.loads(manifest.read_text('utf-8')).get('entries',{}) if manifest.exists() else {}
 pending=[]
 for key,entry in entries().items():
  identity=json.dumps(dict(entry,engine=ENGINE),sort_keys=True,ensure_ascii=False)
  filename=hashlib.sha256(identity.encode()).hexdigest()+'.wav';target=CACHE/filename
  if not target.exists():pending.append((key,entry,filename));continue
  info=sf.info(str(target))
  if info.frames<2400 or info.channels!=1 or info.samplerate!=24000:raise RuntimeError('Invalid existing cache: '+key)
  saved[key]=dict(entry,engine=ENGINE,filename=filename,duration_s=info.duration,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
 if pending:
  print('LOADING MODEL; '+str(len(pending))+' remaining clips',flush=True)
  model=Qwen3TTSModel.from_pretrained(str(MODEL),device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa')
  pending.sort(key=lambda item:(item[1]['language'],len(item[1]['text'])))
  batch_size=int(os.environ.get('HONGIK_TTS_BATCH','3'))
  for position in range(0,len(pending),batch_size):
   batch=pending[position:position+batch_size];start=time.monotonic()
   print('SYNTHESIZING '+','.join(item[0] for item in batch),flush=True)
   with torch.inference_mode():
    torch.manual_seed(184)
    wavs,sr=model.generate_custom_voice(text=[e['text'] for _,e,_ in batch],language=[e['language'] for _,e,_ in batch],
       speaker=[e['speaker'] for _,e,_ in batch],max_new_tokens=min(1536,max(len(e['text']) for _,e,_ in batch)*8+120),do_sample=True)
   for (key,entry,filename),waveform in zip(batch,wavs):
    if sr!=24000 or not .2<len(waveform)/sr<55:raise RuntimeError('Unexpected synthesis duration: '+key)
    target=CACHE/filename;temporary=target.with_suffix('.tmp.wav');sf.write(str(temporary),waveform,sr,subtype='PCM_16');os.replace(temporary,target)
    saved[key]=dict(entry,engine=ENGINE,filename=filename,duration_s=len(waveform)/sr,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
   temporary=CACHE/'manifest.tmp';temporary.write_text(json.dumps(dict(entries=saved),ensure_ascii=False,indent=2),'utf-8');os.replace(temporary,manifest)
   print('BATCH READY '+str(len(saved))+' / '+str(len(entries()))+' in '+str(round(time.monotonic()-start,1))+'s',flush=True)
 print('VOICE CACHE COMPLETE '+str(len(saved)),flush=True)

if __name__=='__main__':main()
