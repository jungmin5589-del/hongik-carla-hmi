"""Offline English synthesis, using already installed local Qwen models only."""
import hashlib,json,os,subprocess,sys,uuid
from pathlib import Path
from english_voice import CACHE,TEXTS,NARRATOR,ACTOR,INSTRUCTION
from prepare_city_audio import COURSE,MODEL

def main():
    if '--worker' not in sys.argv:
        from launch_live import memory_state
        if memory_state()<6:raise RuntimeError('English audio preparation requires 6 GiB commit headroom')
        subprocess.run([str(COURSE/'.tts-env/Scripts/python.exe'),'-u',str(Path(__file__).resolve()),'--worker'],check=True,
                       env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2'),creationflags=0x08000000)
        return
    import gc,torch,soundfile as sf
    from qwen_tts import Qwen3TTSModel
    if not torch.cuda.is_available() or torch.cuda.mem_get_info()[0]<4.5*1024**3:raise RuntimeError('Stop driving first; English audio needs 4.5 GiB free GPU memory')
    torch.set_num_threads(2);CACHE.mkdir(parents=True,exist_ok=True);manifest=CACHE/'manifest.json'
    entries=json.loads(manifest.read_text(encoding='utf-8'))['entries'] if manifest.exists() else {}
    for speaker,engine,model_dir in [('Sohee',NARRATOR,MODEL),('Aiden',ACTOR,Path(__file__).resolve().parents[1]/'cache/models/qwen3-tts-1.7b-customvoice')]:
        model=None
        for key,(text,voice) in TEXTS.items():
            if voice!=speaker:continue
            instruct=INSTRUCTION if speaker=='Aiden' else ''
            identity='\n'.join((engine,'English',speaker,instruct,text));filename=hashlib.sha256(identity.encode()).hexdigest()+'.wav';target=CACHE/filename
            if target.exists():
                info=sf.info(str(target))
                if info.frames<=0 or info.channels!=1 or info.samplerate!=24000:raise RuntimeError('Invalid existing English cache')
            else:
                if model is None:model=Qwen3TTSModel.from_pretrained(str(model_dir),device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa')
                print('Synthesizing English '+key,flush=True)
                with torch.inference_mode():
                    torch.manual_seed(184)
                    wavs,sr=model.generate_custom_voice(text=text,language='English',speaker=speaker,instruct=instruct,
                        max_new_tokens=min(2048,len(text)*6+160),do_sample=True)
                info_duration=len(wavs[0])/sr
                if sr!=24000 or not .3<info_duration<60:raise RuntimeError('Unexpected English audio duration')
                temporary=target.with_suffix('.tmp.wav');sf.write(str(temporary),wavs[0],sr,subtype='PCM_16');os.replace(temporary,target)
            info=sf.info(str(target));entries[key]=dict(filename=filename,text=text,speaker=speaker,language='English',engine=engine,
                instruct=instruct,duration_s=info.duration,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
            temp=CACHE/('manifest-'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(dict(entries=entries),ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,manifest)
            print('Prepared English '+key+' ('+str(round(info.duration,1))+' s)',flush=True)
        del model;gc.collect();torch.cuda.empty_cache()

if __name__=='__main__':main()
