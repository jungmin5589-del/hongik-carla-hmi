"""Existing scene assets aligned to real recorded CARLA events, not speaker capture.

Reuses verified cached dialogue and ports the existing browser's procedural
knock/step/rattle waveforms. Does not invent dialogue or add engine ambience.
"""
import json
import math
import wave
from pathlib import Path

import numpy as np
from scipy.signal import lfilter, resample_poly
from city_voice import audio_path

RATE=48000


def lowpass(a,hz):
    omega=2*np.pi*hz/RATE;cos=np.cos(omega);alpha=np.sin(omega)/(2/math.sqrt(2))
    b=np.array([(1-cos)/2,1-cos,(1-cos)/2])/(1+alpha)
    d=np.array([1,-2*cos/(1+alpha),(1-alpha)/(1+alpha)])
    return lfilter(b,d,a).astype(np.float32)


def pan(a,value,gain=1):
    angle=(value+1)*np.pi/4
    return np.column_stack((a*(gain*np.cos(angle)),a*(gain*np.sin(angle)))).astype(np.float32)


def noise(length,seed):
    a=np.empty(length,dtype=np.float32)
    for i in range(length):
        seed=(seed*1664525+1013904223)&0xffffffff;a[i]=seed/4294967296*2-1
    return a


def door():
    t=np.arange(round(RATE*.38))/RATE
    a=np.minimum(1,t/.0025)*(.6*np.sin(2*np.pi*92*t)*np.exp(-t/.085)+.27*np.sin(2*np.pi*187*t)*np.exp(-t/.045)+.18*np.sin(2*np.pi*327*t)*np.exp(-t/.025)+.13*noise(len(t),619)*np.exp(-t/.012))
    a*=np.minimum(1,(len(t)-np.arange(len(t)))/(RATE*.025))
    return pan(lowpass(a,1500),.85,.32)


def step():
    t=np.arange(round(RATE*.13))/RATE;k=np.log(45/105)/.10
    phase=2*np.pi*105*(np.exp(k*np.minimum(t,.10))-1)/k+2*np.pi*45*np.maximum(0,t-.1)
    gain=.035*np.exp(np.log(.001/.035)*t/.12)
    return pan((np.sin(phase)*gain).astype(np.float32),.8)


def rattle():
    t=np.arange(RATE*4)/RATE
    a=.12*np.sin(t*2*np.pi*48)+noise(len(t),7231)*.4*np.exp(-(t%.23)/.025)
    return np.repeat((lowpass(a,2100)*.14)[:,None],2,axis=1)


def voice(key):
    with wave.open(str(audio_path(key))) as source:
        if source.getsampwidth()!=2 or source.getnchannels()!=1:raise ValueError('Expected verified mono PCM16 dialogue')
        a=np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(np.float32)/32768
        rate=source.getframerate()
    if rate!=RATE:
        divisor=math.gcd(rate,RATE);a=resample_poly(a,RATE//divisor,rate//divisor)
    return pan(lowpass(a,2600),.8,.68)


def render(timeline,duration,output):
    mix=np.zeros((math.ceil(duration*RATE),2),dtype=np.float32)
    events=[];played=[];last_voice=last_knock=0;last_step=-1.;mechanical_start=None
    knock=door();footstep=step();mechanical=None;last_mode=False;busy_until=0.
    def add(at,clip,kind,key=None):
        start=round(at*RATE);skip=max(0,-start);start=max(0,start);n=min(len(clip)-skip,len(mix)-start)
        if n>0:mix[start:start+n]+=clip[skip:skip+n]
        events.append(dict(at_s=at,kind=kind,key=key,duration_s=len(clip)/RATE))
    for item in timeline:
        at=item['recording_s'];state=item['state'];sc=state['scenario'];c=sc.get('context',{});ext=c.get('exterior',{})
        enabled=state['mode']=='auto' and not sc['completed']
        if enabled:
            cue=ext.get('voice_cue') or {};index=cue.get('index',0)
            if index>last_voice:
                last_voice=index;key=cue.get('key')
                if key and not c.get('actor_retreat') and sc['elapsed_s']<=cue.get('expires_s',0):
                    clip=voice(key);when=max(at,busy_until+.8) if busy_until else at
                    if when-at>cue['expires_s']-sc['elapsed_s']:raise RuntimeError('Dialogue cue expired before it could finish')
                    add(when,clip,'cached_dialogue',key);played.append(key);busy_until=when+len(clip)/RATE
            count=ext.get('knock_count',0)
            if count>last_knock:
                if count-last_knock>1:raise RuntimeError('Polling missed a door knock')
                last_knock=count
                if ext.get('at_window'):add(at,knock,'door_knock')
            if sc['id']=='city_carpool' and ext.get('walk_speed_mps',0)>.083 and at-last_step>=.6:
                add(at,footstep,'footstep');last_step=at
            active=c.get('rattle_active',False)
            if active and mechanical_start is None:mechanical_start=at
            if not active and mechanical_start is not None:
                mechanical=rattle() if mechanical is None else mechanical
                start=mechanical_start
                while start<at:
                    clip=mechanical[:max(0,min(len(mechanical),round((at-start)*RATE)))];add(start,clip,'mechanical_rattle');start+=4
                mechanical_start=None
        elif mechanical_start is not None:
            mechanical=rattle() if mechanical is None else mechanical;start=mechanical_start
            while start<at:
                add(start,mechanical[:max(0,min(len(mechanical),round((at-start)*RATE)))],'mechanical_rattle');start+=4
            mechanical_start=None
        last_mode=enabled
    if mechanical_start is not None:
        mechanical=rattle() if mechanical is None else mechanical;start=mechanical_start
        while start<duration:
            add(start,mechanical[:min(len(mechanical),round((duration-start)*RATE))],'mechanical_rattle');start+=4
    if timeline[-1]['state']['profile']=='carpool' and len(played)!=6:raise RuntimeError('Expected all six existing dialogue clips')
    peak=float(np.max(np.abs(mix)));gain=min(1.,.96/max(.96,peak));mix*=gain
    with wave.open(str(output),'wb') as target:
        target.setnchannels(2);target.setsampwidth(2);target.setframerate(RATE)
        target.writeframes((np.clip(mix,-1,1)*32767).astype('<i2').tobytes())
    result=dict(events=events,dialogue=played,peak=peak*gain,rate=RATE,channels=2,normalization_gain=gain,
        scope='Existing cached voices and procedural effects mixed against actual CARLA event timestamps; not captured PC playback',
        engine_ambience_added=False)
    output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
