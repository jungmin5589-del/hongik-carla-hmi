"""Prepare prospective action acknowledgements offline; never synthesize in a drive."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from research_voice import ENGINE,entries
from prepare_city_audio import COURSE,MODEL

def main():
 p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--languages',default='ko,en,zh');p.add_argument('--batch',type=int,default=3);p.add_argument('--worker',action='store_true');p.add_argument('--list',action='store_true');a=p.parse_args()
 languages=set(a.languages.split(','))
 if not languages<={'ko','en','zh'} or not languages or not 1<=a.batch<=3:raise ValueError('Invalid languages or batch size')
 selected={k:v for k,v in entries().items() if k.split('_',1)[0] in languages and '_intent_' in k}
 if a.list:print(json.dumps(selected,ensure_ascii=False,indent=2));return
 if not a.worker:
  from launch_live import memory_state
  if memory_state()<6:raise RuntimeError('Voice preparation requires 6 GiB commit headroom')
  subprocess.run([str(COURSE/'.tts-env/Scripts/python.exe'),'-u',str(Path(__file__).resolve()),'--worker','--cache',str(a.cache),'--languages',a.languages,'--batch',str(a.batch)],check=True,env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2'),creationflags=0x08000000);return
 import torch,soundfile as sf
 from qwen_tts import Qwen3TTSModel
 if not torch.cuda.is_available() or torch.cuda.mem_get_info()[0]<4.5*1024**3:raise RuntimeError('Stop driving first; voice preparation needs 4.5 GiB free GPU memory')
 torch.set_num_threads(2);a.cache.mkdir(parents=True,exist_ok=True);manifest=a.cache/'manifest.json'
 saved=json.loads(manifest.read_text('utf-8')).get('entries',{}) if manifest.exists() else {};pending=[]
 for key,entry in selected.items():
  filename=hashlib.sha256(json.dumps(dict(entry,engine=ENGINE),sort_keys=True,ensure_ascii=False).encode()).hexdigest()+'.wav';target=a.cache/filename
  if target.exists():
   info=sf.info(str(target))
   if info.frames<2400 or info.channels!=1 or info.samplerate!=24000:raise RuntimeError('Invalid existing cache')
   saved[key]=dict(entry,engine=ENGINE,filename=filename,duration_s=info.duration,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
  else:pending.append((key,entry,filename))
 if pending:
  print('LOADING MODEL; '+str(len(pending))+' action clips',flush=True)
  model=Qwen3TTSModel.from_pretrained(str(MODEL),device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa')
  pending.sort(key=lambda item:({'Korean':0,'English':1,'Chinese':2}[item[1]['language']],len(item[1]['text'])))
  for index in range(0,len(pending),a.batch):
   batch=pending[index:index+a.batch];start=time.monotonic();print('SYNTHESIZING '+','.join(k for k,_,_ in batch),flush=True)
   with torch.inference_mode():
    torch.manual_seed(184)
    wavs,sr=model.generate_custom_voice(text=[e['text'] for _,e,_ in batch],language=[e['language'] for _,e,_ in batch],speaker=[e['speaker'] for _,e,_ in batch],max_new_tokens=400,do_sample=True)
   for (key,entry,filename),waveform in zip(batch,wavs):
    duration=len(waveform)/sr
    if sr!=24000 or not .2<duration<15:raise RuntimeError('Unexpected action clip duration: '+key)
    target=a.cache/filename;temp=target.with_suffix('.tmp.wav');sf.write(str(temp),waveform,sr,subtype='PCM_16');os.replace(temp,target)
    saved[key]=dict(entry,engine=ENGINE,filename=filename,duration_s=duration,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
   temp=a.cache/'manifest.intent.tmp';temp.write_text(json.dumps({'entries':saved},ensure_ascii=False,indent=2),'utf-8');os.replace(temp,manifest)
   print('BATCH READY '+str(index+len(batch))+'/'+str(len(pending))+' '+str(round(time.monotonic()-start,1))+'s',flush=True)
 temp=a.cache/'manifest.intent.tmp';temp.write_text(json.dumps({'entries':saved},ensure_ascii=False,indent=2),'utf-8');os.replace(temp,manifest)
 print('ACTION VOICES COMPLETE '+str(len(selected)),flush=True)
if __name__=='__main__':main()
