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

if __name__=='__main__':unittest.main()
