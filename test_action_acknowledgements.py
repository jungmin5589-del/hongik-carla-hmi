"""Action intent copy and audio-duration timing; no driving or model inference."""
import tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
from research_voice import INTENT_LINES,INTENT_ACTIONS,entries,intent_delay
from midterm_study import OPTIONS
class AcknowledgementTests(unittest.TestCase):
 def test_every_executable_option_has_prospective_copy_in_three_languages(self):
  for options in OPTIONS.values():
   for option in options:
    action=option['scenario_action'].removeprefix('request_')
    self.assertIn(action,INTENT_ACTIONS)
    key=INTENT_ACTIONS[action]
    for language in ('ko','en','zh'):self.assertIn(language+'_'+key,entries())
  self.assertNotIn('넓혔어요',INTENT_LINES['intent_gap'][0])
 def test_execution_delay_covers_actual_verified_audio(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ack.wav'
   with wave.open(str(p),'wb') as w:w.setparams((1,2,24000,0,'NONE',''));w.writeframes(b'\0\0'*24000*5)
   with patch('research_voice.audio_path',return_value=p):self.assertAlmostEqual(intent_delay('widen'),5.4)
 def test_missing_audio_preserves_cancellable_delay(self):
  with patch('research_voice.audio_path',side_effect=FileNotFoundError):self.assertEqual(intent_delay('horn'),3.)
