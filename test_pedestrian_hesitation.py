import unittest
from pedestrian_hesitation import hesitation_at,hesitation_target

class HesitationTests(unittest.TestCase):
    def test_visible_half_steps_with_smooth_changes_and_both_directions(self):
        rows=[hesitation_at(i*.01) for i in range(2400)];values=[r['nudge_m'] for r in rows]
        self.assertGreater(max(values),.5);self.assertGreater(sum(r['phase']=='step_back' for r in rows),200)
        self.assertLess(max(abs(b-a) for a,b in zip(values,values[1:])),.015)
        self.assertTrue(all(0<=v<=.54 for v in values))
    def test_waiting_motion_never_becomes_a_full_crossing(self):
        for anchor in [.9,1.5,2.]:
            for t in range(1000):
                target=hesitation_target(anchor,3.,t*.1)['target_offset_m']
                self.assertGreaterEqual(target,.85);self.assertLessEqual(target,3.)
                self.assertLessEqual(abs(hesitation_at(t*.1)['glance_deg']),7.)

if __name__=='__main__':unittest.main()
