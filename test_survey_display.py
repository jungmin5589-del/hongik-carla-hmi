import unittest,threading
from types import SimpleNamespace as NS
from lab_viewer import preview_layout
from native_carla import NativeBridge
class DisplaySurveyTests(unittest.TestCase):
 def test_laptop_only_keeps_preview(self):self.assertEqual(preview_layout([[0,0,2560,1600]]),([40,60],[1200,225],False))
 def test_external_display_uses_center_camera(self):self.assertEqual(preview_layout([[0,0,2560,1600],[2560,0,1920,1080]]),([2560,0],[1920,1080],True))
 def test_left_external_is_supported(self):self.assertEqual(preview_layout([[-1920,0,1920,1080],[0,0,2560,1600]])[0],[-1920,0])
 def test_emergency_stop_blocks_departure_until_finished(self):
  b=NS(lock=threading.RLock(),scenario=NS(session='s',emergency_requested=True),state={})
  with self.assertRaisesRegex(ValueError,'비상 정지'):NativeBridge.control(b,{'mode':'auto'})
if __name__=='__main__':unittest.main()
