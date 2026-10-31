"""Verified local pre-rendered audio for the three city interaction cases."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import wave
from exterior_dialogue import DIALOGUE,VOICE_ENGINE,VOICE_INSTRUCTION

CACHE=Path(__file__).resolve().parents[1]/'cache/city-audio'
TEXTS={
 'city_yield':('보행자가 먼저 가라는 손짓을 하고 있어요. 차량은 횡단 여부를 확인하며 정차하고 있습니다.','Sohee'),
 'city_carpool':('차량 밖에서 고성이 들리고 한 사람이 접근하고 있어요. 문은 잠금 상태이며 예약된 동승자인지는 확인되지 않았습니다.','Sohee'),
 'city_rattle':('차량 하부에서 반복적인 소리가 들리고 있어요. 원인은 아직 확인되지 않았습니다. 현재 차량 상태를 살피고 있습니다.','Sohee'),
 'city_outside':('어, 이 차 아니야? 잠깐만요! 여기요!','Aiden'),
 'city_outside_shout':('거기 안에 사람 있잖아! 잠깐 나와 봐요! 여기요!','Aiden'),
 'city_outside_door':('여기 보라고요! 문 좀 열어 봐요! 잠깐만요!','Aiden'),
 'city_notice':('탑승 예약을 확인해 주세요. 도움이 필요하면 관제에 연결하겠습니다.','Sohee'),
 'city_taxi_warning':('저는 택시가 아닙니다.','Sohee')}
TEXTS.update({key:(text,'Aiden') for _,key,text in DIALOGUE})

@lru_cache(maxsize=24)
def audio_path(key):
 if key not in TEXTS:raise ValueError('Unknown city audio')
 record=json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))['entries'][key]
 if (record['text'],record['speaker'])!=TEXTS[key]:raise ValueError('City audio metadata mismatch')
 if key in {item[1] for item in DIALOGUE} and (record.get('engine')!=VOICE_ENGINE or record.get('instruct')!=VOICE_INSTRUCTION):
  raise ValueError('Exterior acting preset mismatch; prepare_exterior_voice.py is required')
 name=record['filename']
 if Path(name).name!=name or not name.endswith('.wav'):raise ValueError('Invalid city audio path')
 p=CACHE/name
 if hashlib.sha256(p.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('City audio checksum mismatch')
 with wave.open(str(p)) as f:
  if f.getnchannels()!=1 or f.getnframes()==0:raise ValueError('Invalid audio waveform')
 return p

def narration(key):
 text,speaker=TEXTS[key]
 try:
  audio_path(key)
  return dict(text=text,speaker=speaker,cached=True,url='/api/narration/audio/'+key+'.wav')
 except (OSError,ValueError,KeyError,wave.Error):return dict(text=text,speaker=speaker,cached=False,url=None)
