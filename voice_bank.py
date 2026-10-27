"""Authentic pre-rendered Qwen Sohee narration; no inference in the drive process."""
import hashlib
import json
import wave
from functools import lru_cache
from pathlib import Path

CACHE=Path(__file__).resolve().parents[1]/'cache/sohee-narration'
ENGINE='Qwen3-TTS-12Hz-0.6B-CustomVoice:Sohee:Korean:v1'
TEXTS={
 'blockade':'앞차는 시속 30킬로미터로 주행하고 있어요. 오른쪽에는 대형차 세 대가 나란한 속도로 달리고, 왼쪽에는 빠른 차량이 계속 지나가고 있어요. 어떻게 대응할지 선택해 주세요.',
 'congestion':'앞차의 출발과 정지가 반복되고 있어요. 차간 거리를 유지하며 천천히 따라가고 있습니다. 어떻게 대응할지 선택해 주세요.',
 'night':'앞 차량이 차선 경계까지 좌우로 흔들리고 있어요. 앞차와의 거리를 확인하며 주행하고 있습니다. 어떻게 대응할지 선택해 주세요.',
 'fog':'전방에 안개가 짙어지고 있어요. 속도를 낮추고 앞차와의 간격을 확보하며 주행하고 있습니다. 어떻게 대응할지 선택해 주세요.',
 'normal':'현재 주행 상황을 살펴보고 있어요. 변화가 있으면 대응 방법을 함께 안내할게요.',
 'complete':'목적지에 도착했습니다.'}

@lru_cache(maxsize=1)
def catalog():
    manifest=json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))
    entries=manifest['entries'];assert manifest['engine']==ENGINE
    for key,text in TEXTS.items():
        record=entries[key]
        if record['text']!=text or record['engine']!=ENGINE or record['speaker']!='Sohee':
            raise ValueError('Sohee narration metadata mismatch')
        path=CACHE/record['filename']
        if path.parent!=CACHE or path.suffix!='.wav':raise ValueError('Invalid narration file')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Sohee audio checksum mismatch')
        with wave.open(str(path),'rb') as audio:
            if audio.getnchannels()!=1 or audio.getnframes()<=0:raise ValueError('Invalid Sohee waveform')
    return entries

def narration(profile,active,completed=False):
    key='complete' if completed else profile if active else 'normal'
    try:
        record=catalog()[key]
        return dict(key=key,text=record['text'],speaker='Sohee',engine=ENGINE,
            url='/api/narration/audio/'+key+'.wav',cached=True)
    except (OSError,ValueError,KeyError,AssertionError,wave.Error):
        return dict(key=key,text=TEXTS[key],speaker='Sohee',url=None,cached=False)

def audio_path(key):
    if key not in TEXTS:raise ValueError('Unknown narration')
    return CACHE/catalog()[key]['filename']
