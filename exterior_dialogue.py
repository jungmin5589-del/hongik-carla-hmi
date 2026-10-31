"""Finite dialogue, timed from confirmed close-range attention, never from startup."""
VOICE_ENGINE='Qwen3-TTS-12Hz-1.7B-CustomVoice'
VOICE_INSTRUCTION=('A furious, heavily intoxicated man confronting someone inside a taxi. '
 'Speak Korean with a very angry, confrontational raised voice, rough breath, impatient sharp attacks '
 'and irregular pauses. Slightly slurred but clearly intelligible. Bark the short commands. '
 'No polite announcer tone, no laughter, no narration. Speak only the provided Korean text.')
DIALOGUE=(
 (0.,'city_taxi_call','택시! 우리 집으로!'),
 (8.,'city_taxi_refusal','문 열어! 문!'),
 (18.,'city_taxi_complaint','뭐야, 지금 승차 거부 하는 거야? 어?'),
 (30.,'city_taxi_plate','너 번호판 뭐야? 가만있어 봐. 번호판 좀 보자.'),
 (44.,'city_taxi_door','야! 안에 있는 거 다 보여! 문 열어!'),
 (58.,'city_taxi_answer','내 말 안 들려? 지금 나 무시하는 거냐고!'))

class AttentionGate:
 def __init__(self):self.started_at=None;self.settled=0.
 def tick(self,dt,elapsed,distance,facing_error,speed,retreat=False):
  if self.started_at is not None or retreat:return self.started_at
  ready=distance<=.38 and abs(facing_error)<=18. and speed<.15
  self.settled=self.settled+min(.15,max(0.,dt)) if ready else 0.
  if self.settled>=.65:self.started_at=elapsed
  return self.started_at

def dialogue_cue(elapsed,retreat=False,started_at=None,door_speech_at=None):
 if retreat or started_at is None or elapsed<started_at:return dict(index=0,key=None,expires_s=0.)
 if door_speech_at is None or elapsed<door_speech_at:
  expires=min(started_at+7.,door_speech_at-.1) if door_speech_at is not None else started_at+7.
  return dict(index=1,key=DIALOGUE[0][1] if elapsed<=expires else None,expires_s=expires)
 relative=elapsed-door_speech_at+DIALOGUE[1][0]
 i=max(i for i,(at,_,_) in enumerate(DIALOGUE) if relative>=at)
 expires=door_speech_at+((DIALOGUE[i+1][0]-1.) if i+1<len(DIALOGUE) else DIALOGUE[-1][0]+10.)-DIALOGUE[1][0]
 return dict(index=i+1,key=DIALOGUE[i][1] if elapsed<=expires else None,expires_s=expires)
