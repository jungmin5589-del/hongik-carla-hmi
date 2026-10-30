"""Finite taxi-misidentification performance; each line is scheduled once per trial."""
DIALOGUE=(
 (5.,'city_taxi_call','어이, 택시! 야, 택시!'),
 (13.,'city_taxi_refusal','야, 승차 거부 하냐? 택시가?'),
 (24.,'city_taxi_complaint','와, 택시가 승차 거부를 해 버리네.'),
 (38.,'city_taxi_plate','어? 너 번호판 뭐야? 번호판 좀 보자.'),
 (54.,'city_taxi_door','야! 안에 사람 있잖아. 문 좀 열어 봐!'),
 (72.,'city_taxi_answer','어이! 말 좀 해 봐. 나 지금 얘기하잖아!'))

def dialogue_cue(elapsed,retreat=False):
 if retreat or elapsed< DIALOGUE[0][0]:return dict(index=0,key=None,expires_s=0.)
 i=max(i for i,(at,_,_) in enumerate(DIALOGUE) if elapsed>=at)
 expires=DIALOGUE[i+1][0]-1. if i+1<len(DIALOGUE) else 82.
 return dict(index=i+1,key=DIALOGUE[i][1] if elapsed<=expires else None,expires_s=expires)
