import unittest
from vehicle_following import following_speed,imminent_contact,longitudinal
class FollowingTests(unittest.TestCase):
 def test_stopped_leader_demands_braking_before_contact(self):
  self.assertLess(following_speed(10.,0.,10.,7.,10.),7.)
  self.assertTrue(imminent_contact(10.,0.,10.))
 def test_closing_gap_never_raises_target_above_braking_bound(self):
  values=[following_speed(15.,5.,gap,7.,25.) for gap in (2.,4.,8.,16.,40.)]
  self.assertEqual(values,sorted(values));self.assertEqual(values[0],0.)
 def test_emergency_and_pause_override_positive_acceleration(self):
  self.assertEqual(longitudinal(8.,25.,25.,.1,True),(0.,1.,0.))
  self.assertEqual(longitudinal(8.,25.,25.,.1,running=False),(0.,1.,0.))
 def test_overspeed_uses_brake_instead_of_old_integral(self):
  throttle,brake,_=longitudinal(12.,8.,8.,.1)
  self.assertEqual(throttle,0.);self.assertGreater(brake,0.)
 def test_departure_acceleration_is_limited(self):
  self.assertLessEqual(longitudinal(0.,25.,0.,.1)[2],.16+.0001)

 def test_paused_alignment_time_does_not_count_as_driving_delay(self):
  from vehicle_following import driving_step
  self.assertEqual(driving_step(1.,8.,False,True),0.)
  self.assertAlmostEqual(driving_step(8.,8.1,True,True),.1)
  self.assertEqual(driving_step(8.,9.,True,True),1.)

 def test_small_comfort_deceleration_never_applies_positive_throttle(self):
  throttle,brake,_=longitudinal(8.,7.88,8.,.1)
  self.assertEqual(throttle,0.);self.assertGreater(brake,0.)
