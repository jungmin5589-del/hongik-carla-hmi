"""Authentic cached Sohee lines, isolated from the existing voice bank."""
import hashlib
import json
from pathlib import Path
import wave
from functools import lru_cache

CACHE=Path(__file__).resolve().parents[1]/'cache/sohee-pedestrian'
ENGINE='Qwen3-TTS-12Hz-0.6B-CustomVoice:Sohee:Korean:v1'
TEXTS={
    'yield':'보행자가 먼저 가라는 손짓을 하고 있어요. 차량은 보행자가 건널 가능성이 있어 정차하고 있습니다. 양보 안내를 보내거나 관제 확인을 요청할 수 있어요.',
    'yield_notice':'차량이 기다리고 있습니다.'}

@lru_cache(maxsize=2)
def audio_path(key):
    if key not in TEXTS:raise ValueError('Unknown pedestrian narration')
    record=json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))['entries'][key]
    if record['text']!=TEXTS[key] or record['engine']!=ENGINE or record['speaker']!='Sohee':raise ValueError('Pedestrian voice metadata mismatch')
    name=record['filename']
    if Path(name).name!=name or not name.endswith('.wav'):raise ValueError('Invalid audio path')
    path=CACHE/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Pedestrian voice checksum mismatch')
    with wave.open(str(path)) as audio:
        if audio.getnchannels()!=1 or audio.getnframes()<=0:raise ValueError('Invalid waveform')
    return path

def narration(key):
    try:
        audio_path(key)
        return dict(text=TEXTS[key],speaker='Sohee',cached=True,url='/api/narration/audio/'+key+'.wav')
    except (OSError,ValueError,KeyError,wave.Error):
        return dict(text=TEXTS[key],speaker='Sohee',cached=False,url=None)
