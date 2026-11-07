"""English counterpart of the existing cached voices. No runtime inference."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import wave

CACHE=Path(__file__).resolve().parents[1]/'cache/english-audio'
NARRATOR='Qwen3-TTS-12Hz-0.6B-CustomVoice'
ACTOR='Qwen3-TTS-12Hz-1.7B-CustomVoice'
INSTRUCTION=('An angry, intoxicated man confronting someone inside a taxi. Speak English with a rough, raised, impatient voice, '
             'slightly slurred but intelligible, sharp attacks and irregular pauses. No laughter or announcer tone. Say only the supplied words.')
TEXTS={
 'blockade':('The car ahead and the three large vehicles on our right are moving slowly. Fast traffic keeps passing on the left. We are maintaining our gap and checking for space. What would you like to do?','Sohee'),
 'congestion':('The car ahead is stopping and starting. We are following slowly and maintaining our distance. What would you like to do?','Sohee'),
 'night':('The car ahead is swaying from side to side near the lane markings. We are staying in our lane and monitoring the gap. What would you like to do?','Sohee'),
 'fog':('Dense fog is limiting visibility ahead. We are slowing down and maintaining our distance from the car ahead. What would you like to do?','Sohee'),
 'normal':('I am checking the driving conditions. You can review the current situation here.','Sohee'),
 'complete':('You have arrived at your destination.','Sohee'),
 'city_yield':('The pedestrian is hesitating beside the crossing and gesturing for us to go first. We have stopped and are checking whether they intend to cross. What would you like to do?','Sohee'),
 'city_carpool':('Someone is shouting outside and approaching the car. The doors remain locked. We have not confirmed whether this is your booked passenger. What would you like to do?','Sohee'),
 'city_rattle':('There is a recurring scraping or rattling sound from outside the vehicle. The cause has not been confirmed. We are checking the current driving conditions. What would you like to do?','Sohee'),
 'city_cargo':('An object has fallen from the truck ahead, and we are slowing down. Its type and whether we can safely pass are not yet confirmed. What would you like to do?','Sohee'),
 'yield_notice':('Please go ahead and cross. We will wait.','Sohee'),
 'city_notice':('Please check your booking. Assistance can be requested if you need help.','Sohee'),
 'city_taxi_warning':('This vehicle is not a taxi.','Sohee'),
 'city_taxi_call':('Taxi! Take me home!','Aiden'),
 'city_taxi_refusal':('Open the door! Open it!','Aiden'),
 'city_taxi_complaint':('What? Are you refusing to take me? Huh?','Aiden'),
 'city_taxi_plate':('What is your plate number? Hold on. Let me see that plate.','Aiden'),
 'city_taxi_door':('Hey! I can see you in there! Open the door!','Aiden'),
 'city_taxi_answer':('Can you hear me? Are you ignoring me?','Aiden'),
 'city_outside':('Hey, is this my ride? Wait a minute! Over here!','Aiden'),
 'city_outside_shout':('I can see someone in there! Come out here! Hey!','Aiden'),
 'city_outside_door':('Look over here! Open the door! Wait a minute!','Aiden')}

ALIASES={'yield':'city_yield','city_fog':'fog'}
def canonical(key):return ALIASES.get(key,key)

@lru_cache(maxsize=32)
def audio_path(key):
    key=canonical(key)
    if key not in TEXTS:raise ValueError('Unknown English voice')
    entry=json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))['entries'][key]
    text,speaker=TEXTS[key];engine=ACTOR if speaker=='Aiden' else NARRATOR
    if (entry['text'],entry['speaker'],entry['language'],entry['engine'])!=(text,speaker,'English',engine):raise ValueError('English audio metadata mismatch')
    name=entry['filename']
    if Path(name).name!=name or not name.endswith('.wav'):raise ValueError('Invalid English audio filename')
    p=CACHE/name
    if hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('English audio checksum mismatch')
    with wave.open(str(p)) as f:
        if f.getnchannels()!=1 or f.getnframes()<=0 or f.getframerate()!=24000:raise ValueError('Invalid English waveform')
    return p

def catalog():
    out={}
    for key,(text,speaker) in TEXTS.items():
        try:audio_path(key);cached=True
        except (OSError,ValueError,KeyError,wave.Error):cached=False
        out[key]=dict(text=text,speaker=speaker,cached=cached,url='/api/english-audio/'+key+'.wav' if cached else None)
    for alias,key in ALIASES.items():out[alias]=out[key]
    return out
