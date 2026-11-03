"""Verified, softened real metal friction; audio stays in the external cache."""
import hashlib,json,wave
from pathlib import Path
from functools import lru_cache
CACHE=Path(__file__).resolve().parent.parent/'cache'/'mechanical-recording'

@lru_cache(maxsize=1)
def audio():
    record=json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))
    if record['filename']!='soft-metal-scrape.wav' or record['license']!='CC-BY-4.0':raise ValueError('Invalid sound provenance')
    path=CACHE/'soft-metal-scrape.wav'
    data=path.read_bytes()
    if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Sound integrity mismatch')
    with wave.open(str(path)) as w:
        if w.getnchannels()!=1 or w.getsampwidth()!=2 or not 1<w.getnframes()/w.getframerate()<4:raise ValueError('Invalid waveform')
    return data

def metadata():
    try:audio();ready=True
    except (OSError,ValueError,KeyError,wave.Error):ready=False
    return dict(available=ready,url='/api/mechanical-audio/scrape.wav',title='Metal Scraping.wav',author='Doctor_Jekyll',
        source='https://freesound.org/people/Doctor_Jekyll/sounds/254064/',license='CC-BY-4.0',
        changes='Excerpt; high-frequency attenuation, lower level and edge fades. Not a recorded vehicle fault.')
