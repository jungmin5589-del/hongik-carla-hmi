import unittest
from unittest.mock import patch
import launch_live

class StartMemoryTests(unittest.TestCase):
    def check(self,values,timeout):
        clock=[0.]
        def sleep(seconds):clock[0]+=seconds
        with patch.object(launch_live,'memory_state',side_effect=values),patch.object(launch_live.time,'monotonic',side_effect=lambda:clock[0]),patch.object(launch_live.time,'sleep',side_effect=sleep):
            return launch_live.require_startup_memory(timeout),clock[0]
    def test_exact_floor_starts_without_waiting(self):self.assertEqual(self.check([16.],2),(16.,0.))
    def test_released_memory_can_be_reclaimed_without_lowering_the_floor(self):self.assertEqual(self.check([14.,15.,16.5],3),(16.5,2.))
    def test_low_memory_still_refuses_after_bounded_wait(self):
        with self.assertRaisesRegex(RuntimeError,'16 GiB'):self.check([14.,14.,14.],2)

if __name__=='__main__':unittest.main()
