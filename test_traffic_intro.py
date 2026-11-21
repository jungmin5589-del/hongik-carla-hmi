import unittest,tempfile
from pathlib import Path
from native_carla import NativeScenario
from traffic_intro import lead_targets,following_gap,truck_formation
class IntroTests(unittest.TestCase):
 def test_normal_thirty_seconds_then_continuous_change(self):
  for profile in ('congestion','night'):
   self.assertEqual(lead_targets(profile,0),(35.,0.))
   self.assertEqual(lead_targets(profile,29.999),(35.,0.))
   self.assertEqual(following_gap(profile,29.999),24.)
   self.assertLess(abs(lead_targets(profile,30.001)[1]),.00001)
   for t in (30,40,45,50,55,60,65,70):
    before=lead_targets(profile,t-.001);after=lead_targets(profile,t+.001)
    self.assertLess(abs(before[0]-after[0]),.01);self.assertLess(abs(before[1]-after[1]),.01)
  self.assertEqual(following_gap('congestion',45),5.5)
  self.assertEqual(following_gap('night',45),6.5)
 def test_pausing_does_not_advance_onset(self):
  with tempfile.TemporaryDirectory() as d:
   for profile in ('congestion','night'):
    sc=NativeScenario(profile,Path(d)/(profile+'.jsonl'))
    try:
     self.assertEqual(sc.desired_gap,24.)
     sc.tick(29.9,True,35,24);self.assertFalse(sc.onset)
     sc.tick(50,False,0,24);self.assertFalse(sc.onset)
     sc.tick(.2,True,35,24);self.assertTrue(sc.onset);self.assertAlmostEqual(sc.onset_elapsed,30.1)
    finally:sc.events.close()
 def test_truck_columns_keep_spacing_through_transition(self):
  for t in range(90):
   positions=[truck_formation(x,t) for x in (-13.,2.,17.)]
   self.assertAlmostEqual(positions[1]-positions[0],15.)
   self.assertAlmostEqual(positions[2]-positions[1],15.)
 def test_stagger_is_longitudinal_and_keeps_each_column_spacing(self):
  for t in (0,29,30,35,45,90):
   a=[truck_formation(x,t,1) for x in (-13.,2.,17.)]
   b=[truck_formation(x,t,2) for x in (-13.,2.,17.)]
   for left,right in zip(a,b):self.assertAlmostEqual(right-left,6.)
   for column in (a,b):self.assertTrue(all(y-x>=14.99 for x,y in zip(column,column[1:])))
if __name__=='__main__':unittest.main()
