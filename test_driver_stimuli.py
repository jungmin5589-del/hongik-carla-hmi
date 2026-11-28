import math,unittest
from types import SimpleNamespace as NS
from native_alignment import actor_route_distance
from traffic_intro import lead_targets,fast_positions,FAST_CYCLE,limited_offset

class DriverStimulusTests(unittest.TestCase):
 def test_normal_intro_and_practice_stay_unchanged(self):
  for p in ('congestion','night'):
   for t in (0.,15.,29.9):self.assertEqual(lead_targets(p,t),(35.,0.))
   for t in (0.,70.,150.):self.assertEqual(lead_targets(p,t,True),(30.,0.))
 def test_unstable_speeds_and_paths_are_bounded_and_continuous(self):
  for p in ('congestion','night'):
   rows=[lead_targets(p,t/10.) for t in range(3001)]
   self.assertGreater(max(v for v,o in rows[400:])-min(v for v,o in rows[400:]),14.)
   self.assertTrue(all(8.<v<46. for v,o in rows))
   for (v,o),(v2,o2) in zip(rows,rows[1:]):
    self.assertLess(abs(v2-v),1.1);self.assertLess(abs(o2-o),.09)
   if p=='congestion':self.assertLessEqual(max(abs(o) for v,o in rows),.71)
 def test_horn_response_cannot_snap_the_lead_sideways(self):
  self.assertEqual(limited_offset(2.2,1.6,0.),2.2)
  self.assertAlmostEqual(limited_offset(2.2,1.6,.04),2.18)
  self.assertAlmostEqual(limited_offset(1.6,2.2,.04),1.62)
 def test_distant_rear_traffic_never_uses_ego_local_window(self):
  route=NS(length=1000.,project=lambda xy,previous:(200. if previous is None else 420.,0.))
  self.assertEqual(actor_route_distance(route,[200.,0.],500.,200.),200.)
  self.assertEqual(actor_route_distance(route,[200.,0.],500.),200.)
 def test_platoons_have_variation_and_real_openings(self):
  rows=fast_positions();gaps=[b-a for a,b in zip(rows,rows[1:])]+[rows[0]+FAST_CYCLE-rows[-1]]
  self.assertEqual(len(rows),24);self.assertGreater(len(set(gaps)),4)
  self.assertGreaterEqual(min(gaps),16.);self.assertGreater(max(gaps),180.)

if __name__=='__main__':unittest.main()
