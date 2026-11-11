import unittest
from passing_traffic import advance_passing
class PassingTests(unittest.TestCase):
    def test_slow_control_cycle_still_advances_at_90kph(self):
        self.assertAlmostEqual(advance_passing(100,100,90,.6,24),115.)
    def test_continuous_stream_stays_beside_ego_for_five_minutes(self):
        ego=100.;cars=[ego-65+i*13 for i in range(24)]
        for _ in range(600):
            ego+=30/3.6*.5;cars=[advance_passing(s,ego,90,.5,24) for s in cars]
            self.assertTrue(any(0<s-ego<20 for s in cars))
            self.assertTrue(all(-80<=s-ego<232 for s in cars))
    def test_far_behind_vehicles_rejoin_the_stream(self):
        s=advance_passing(-1000,500,90,.5,24);self.assertTrue(420<=s<732)
