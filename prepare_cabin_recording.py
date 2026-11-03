"""Download the CC0 real-car interior recording once; no inference required."""
import hashlib
import json
import os
import time
import urllib.request
from cabin_recording import CACHE,FILENAME,verified

URL='https://bigsoundbank.com/UPLOAD/mp3/3099.mp3'
SHA256='9078b9eb4464864324f8821007a8b780778033aa81e6d464a2701dbd0d70435f'
RECORD=dict(filename=FILENAME,title='Car interior, 50 km/h',author='Joseph SARDIN & Axeline T.',
    license='CC0-1.0',source_url='https://bigsoundbank.com/car-interior-50-km-h-s3099.html',
    download_url=URL,sha256=SHA256,provenance='Real Citroen C3 petrol interior recording; not NuRec location audio',
    duration_s=241.,use='Continuous recording at original pitch; speed-based gain and overlap at loop boundary')


def prepare():
    CACHE.mkdir(parents=True,exist_ok=True);path=CACHE/FILENAME
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=SHA256:
        temp=CACHE/(FILENAME+'.download');deadline=time.monotonic()+300
        try:
            with urllib.request.urlopen(URL,timeout=20) as r,temp.open('wb') as out:
                size=0
                while block:=r.read(65536):
                    size+=len(block)
                    if size>16*1024*1024 or time.monotonic()>deadline:raise ValueError('Recording download limit')
                    out.write(block)
            if hashlib.sha256(temp.read_bytes()).hexdigest()!=SHA256:raise ValueError('Source changed: verify provenance before updating the pinned hash')
            os.replace(temp,path)
        finally:
            if temp.is_file():temp.unlink()
    (CACHE/'manifest.json').write_text(json.dumps(RECORD,ensure_ascii=False,indent=2),encoding='utf-8')
    verified.cache_clear();verified()
    print('Verified real interior recording is ready (CC0; external cache).')


if __name__=='__main__':prepare()
