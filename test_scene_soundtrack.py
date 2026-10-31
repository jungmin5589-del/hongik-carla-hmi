"""Validate missing-cue rejection and synchronization boundaries, not perception."""
import json
import unittest
import uuid
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scene_soundtrack import render,RATE

ROOT=Path(__file__).resolve().parent

def sample(at,profile='night',key=None,index=0,rattle=False,completed=False):
    return dict(recording_s=at,state=dict(profile=profile,mode='auto',scenario=dict(id='city_'+profile,completed=completed,
        elapsed_s=at,context=dict(rattle_active=rattle,exterior=dict(voice_cue=dict(index=index,key=key,expires_s=100),walk_speed_mps=0,knock_count=0)))))

class SoundtrackTests(unittest.TestCase):
    def output(self):
        folder=ROOT/'validation'/('soundtrack-'+uuid.uuid4().hex);folder.mkdir();return folder/'sound.wav'
    def test_no_invented_engine_or_dialogue_for_silent_scene(self):
        path=self.output();result=render([sample(0),sample(2,completed=True)],3,path)
        self.assertEqual(result['peak'],0);self.assertFalse(result['events']);self.assertFalse(result['engine_ambience_added'])
        with wave.open(str(path)) as f:self.assertEqual(f.getnframes(),RATE*3)
    def test_does_not_call_incomplete_dialogue_a_complete_recording(self):
        path=self.output()
        with patch('scene_soundtrack.voice',return_value=np.zeros((RATE//10,2),dtype=np.float32)):
            with self.assertRaisesRegex(RuntimeError,'all six'):render([sample(1,'carpool','city_taxi_call',1),sample(2,'carpool',completed=True)],3,path)
        self.assertFalse(path.exists())
    def test_mechanical_sound_starts_and_stops_with_actual_event(self):
        path=self.output();result=render([sample(0,'rattle'),sample(.8,'rattle',rattle=True),sample(1.4,'rattle'),sample(2,'rattle',completed=True)],2.2,path)
        with wave.open(str(path)) as f:a=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2)
        self.assertEqual(np.max(np.abs(a[:round(.8*RATE)])),0)
        self.assertGreater(np.max(np.abs(a[round(.8*RATE):round(1.4*RATE)])),100)
        self.assertEqual(np.max(np.abs(a[round(1.4*RATE):])),0)
    def test_new_cover_sound_uses_short_contacts_and_stops_when_stationary(self):
        path=self.output();timeline=[sample(0,'rattle'),sample(.5,'rattle',rattle=True),sample(2,'rattle',rattle=True),sample(3,'rattle')]
        for item in timeline:
            item['state']['speed_kph']=18
            item['state']['scenario']['context']['sound_kind']='loose_underbody_cover'
            item['state']['scenario']['context']['exterior']=None
        result=render(timeline,3.2,path)
        hits=[e for e in result['events'] if e['kind']=='underbody_cover']
        self.assertGreater(len(hits),1);self.assertTrue(all(e['duration_s']<=.24 for e in hits))
        self.assertFalse(any(e['kind']=='mechanical_rattle' for e in result['events']))

if __name__=='__main__':unittest.main()
