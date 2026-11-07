"""Verified real shoe contacts; no generated oscillator fallback."""
import hashlib,json,wave
from functools import lru_cache
from pathlib import Path
CACHE=Path(__file__).resolve().parents[1]/'cache/recorded-footsteps'
SOURCE='https://bigsoundbank.com/footsteps-shoe-on-concrete-s0514.html'
@lru_cache(maxsize=1)
def verified():
    record=json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))
    if record['filename']!='steps.wav' or record['license']!='CC0-1.0' or record['source_url']!=SOURCE:raise ValueError('Invalid footstep provenance')
    p=CACHE/'steps.wav'
    if hashlib.sha256(p.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Footstep checksum mismatch')
    with wave.open(str(p)) as w:
        if w.getnchannels()!=1 or w.getframerate()!=24000 or not 0<w.getnframes()/24000<2:raise ValueError('Invalid footstep bank')
    return p,record
def catalog():
    try:
        _,r=verified();return dict(available=True,url='/api/footsteps/bank.wav',segments=r['segments'],source_url=SOURCE,author=r['author'],license=r['license'])
    except (OSError,ValueError,KeyError,wave.Error):return dict(available=False)
