"""Prepare the user's selected real scrape, softened without changing pitch."""
import argparse,hashlib,json,shutil,subprocess,urllib.request,wave
from pathlib import Path
import numpy as np
from scipy.signal import butter,sosfilt
from mechanical_recording import CACHE,audio,metadata
URL='https://cdn.freesound.org/previews/254/254064_2953000-hq.mp3'
HASH='263b6b545b71b38b9ef899e05f9228e1c8abd22db4e74c7b1a0cb4ada6e4d396'

def prepare(ffmpeg,source=None):
    CACHE.mkdir(exist_ok=True,parents=True);p=CACHE/'source-preview.mp3'
    if source:
        source=Path(source)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=HASH:raise ValueError('Source checksum mismatch')
        shutil.copyfile(source,p)
    if not p.is_file():
        with urllib.request.urlopen(URL,timeout=20) as r:p.write_bytes(r.read(1024*1024))
    if hashlib.sha256(p.read_bytes()).hexdigest()!=HASH:raise ValueError('Source changed; verify before updating hash')
    raw=subprocess.check_output([ffmpeg,'-v','error','-i',str(p),'-f','f32le','-ac','1','-ar','48000','-'])
    a=np.frombuffer(raw,dtype='<f4').copy()[round(.12*48000):round(2.82*48000)]
    a=sosfilt(butter(2,[110,1450],fs=48000,btype='bandpass',output='sos'),a)
    n=round(.14*48000);a[:n]*=np.linspace(0,1,n);a[-n:]*=np.linspace(1,0,n)
    a*=min(.024/max(np.sqrt(np.mean(a*a)),1e-9),.16/max(np.max(np.abs(a)),1e-9))
    target=CACHE/'soft-metal-scrape.wav'
    with wave.open(str(target),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes((a*32767).astype('<i2').tobytes())
    record=metadata();record.pop('available',None);record.update(filename=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),source_sha256=HASH,
        processing=dict(highpass_hz=110,lowpass_hz=1450,rms=float(np.sqrt(np.mean(a*a))),peak=float(np.max(np.abs(a))),duration_s=len(a)/48000))
    (CACHE/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');audio.cache_clear();audio()
    print('Ready: softened real scrape, original pitch, occasional playback; external cache.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ffmpeg',default=shutil.which('ffmpeg'));ap.add_argument('--source');args=ap.parse_args()
    if not args.ffmpeg:ap.error('Supply an existing FFmpeg executable with --ffmpeg')
    prepare(args.ffmpeg,args.source)
