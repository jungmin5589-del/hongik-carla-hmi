"""Offline extraction of four real shoe contacts from an attributed CC0 source."""
import hashlib,json,urllib.request
from pathlib import Path
from footstep_recording import CACHE,SOURCE
SHA='a1ef81474981815bf31ec022cb8a338a454c0b5d40f3364ec0a2c662eb5f2bed'
def main():
    import numpy as np,soundfile as sf
    from scipy.signal import find_peaks,sosfilt,butter,resample_poly
    CACHE.mkdir(exist_ok=True);raw=CACHE/'0514.mp3'
    if not raw.is_file():urllib.request.urlretrieve('https://bigsoundbank.com/UPLOAD/mp3/0514.mp3',raw)
    if hashlib.sha256(raw.read_bytes()).hexdigest()!=SHA:raise ValueError('Footstep source changed')
    x,rate=sf.read(str(raw));x=x.mean(axis=1) if x.ndim>1 else x
    x=sosfilt(butter(2,[130,4000],btype='bandpass',fs=rate,output='sos'),x)
    window=round(rate*.012);energy=np.sqrt(np.convolve(x*x,np.ones(window)/window,mode='same'))
    peaks,_=find_peaks(energy,distance=round(rate*.3),prominence=energy.max()*.16)
    peaks=[p for p in peaks if rate<p<len(x)-rate];peaks=sorted(sorted(peaks,key=lambda p:energy[p],reverse=True)[:4])
    if len(peaks)!=4:raise ValueError('Four distinct shoe contacts required')
    segments=[];clips=[]
    for i,p in enumerate(peaks):
        a=x[p-round(.045*rate):p+round(.235*rate)].copy();a*=.56/max(.001,np.max(np.abs(a)))
        n=round(rate*.008);a[:n]*=np.linspace(0,1,n);n=round(rate*.035);a[-n:]*=np.linspace(1,0,n)
        a=resample_poly(a,24000,rate);clips.append(a);segments.append(dict(offset=i*.28,duration=.28,source_peak_s=round(p/rate,4)))
    target=CACHE/'steps.wav';sf.write(str(target),np.concatenate(clips),24000,subtype='PCM_16')
    record=dict(filename='steps.wav',sha256=hashlib.sha256(target.read_bytes()).hexdigest(),source_sha256=SHA,source_url=SOURCE,
        author='Joseph SARDIN',license='CC0-1.0',segments=segments,changes='Four isolated contacts; band-limited, normalized and faded; stride playback follows actor movement, not original running cadence')
    (CACHE/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('Prepared four recorded shoe contacts; no runtime synthesis')
if __name__=='__main__':main()
