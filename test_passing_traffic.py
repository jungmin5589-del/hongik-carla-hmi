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


class PhysicalPassingTests(unittest.TestCase):
    def test_visible_traffic_is_never_repositioned(self):
        from passing_traffic import recycle_destination
        for relative in (-100.,-20.,0.,20.,100.,232.):
            self.assertIsNone(recycle_destination(100+relative,100,24,[]))

    def test_forward_exit_recycles_behind_preserving_overshoot(self):
        from passing_traffic import recycle_destination
        self.assertAlmostEqual(recycle_destination(333.,100.,24,[]),21.)

    def test_occupied_rear_slot_defers_recycle(self):
        from passing_traffic import recycle_destination
        self.assertIsNone(recycle_destination(333.,100.,24,[25.]))
