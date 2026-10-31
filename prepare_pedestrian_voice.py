"""One-time local Qwen synthesis, never run by the driving process."""
import hashlib
import json
import shutil
import sys
import time
from navigation_adapter import COURSE
from pedestrian_voice import CACHE, ENGINE, TEXTS

def main():
    from launch_live import memory_state
    if memory_state()<4:raise RuntimeError('Voice preparation needs 4 GiB commit headroom')
    sys.path.insert(0,str(COURSE))
    from sohee_tts import SoheeTTS
    service=SoheeTTS(COURSE)
    try:
        for text in TEXTS.values():
            if not service.cached(text):
                service._start()
                service.process.stdin.write(json.dumps({'text':text},ensure_ascii=False)+'\n');service.process.stdin.flush()
                result=service.lines.get(timeout=720)
                if result.get('error'):raise RuntimeError(result['error'])
                if not service.cached(text):raise RuntimeError('Sohee synthesis did not produce a valid cache')
                print('Prepared Sohee line',flush=True)
        entries={};CACHE.mkdir(parents=True,exist_ok=True)
        for key,text in TEXTS.items():
            name=service.key_func(text)+'.wav';source=service.cache/name
            metadata=json.loads(source.with_suffix('.json').read_text(encoding='utf-8'))
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            if metadata['engine']!=ENGINE or metadata['sha256']!=digest:raise ValueError('Voice metadata mismatch')
            target=CACHE/name
            if not target.exists():shutil.copy2(source,target)
            entries[key]=dict(filename=name,text=text,engine=ENGINE,speaker='Sohee',sha256=digest)
        manifest=CACHE/'manifest.json'
        if manifest.exists():shutil.copy2(manifest,CACHE/('manifest-before-'+time.strftime('%Y%m%d-%H%M%S')+'.json'))
        manifest.write_text(json.dumps(dict(entries=entries),ensure_ascii=False,indent=2),encoding='utf-8')
        print('Pedestrian Sohee cache ready',flush=True)
    finally:service.close()

if __name__=='__main__':main()
