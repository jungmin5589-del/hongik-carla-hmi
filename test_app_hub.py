"""Menu selection must be bounded, idempotent, and never launch two scenes."""
import threading
import time
import unittest
from app_hub import Coordinator

class HubTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.release=threading.Event()
        def runner(job,profile,duration):
            self.calls.append((job,profile,duration));self.release.wait(2)
            self.hub.publish(job,phase='ready')
        self.hub=Coordinator(runner)
    def tearDown(self):self.release.set()
    def body(self,profile='fog',duration=300,request='one'):
        return dict(profile=profile,duration_s=duration,request_id=request)
    def test_duplicate_does_not_launch_again(self):
        body=self.body();a=self.hub.select(body);self.assertEqual(a,self.hub.select(body))
        with self.assertRaises(ValueError):self.hub.select(self.body('night',request='one'))
        self.release.set()
        for _ in range(50):
            if self.hub.state()['phase']=='ready':break
            time.sleep(.01)
        self.assertEqual(len(self.calls),1)
    def test_only_one_profile_can_prepare(self):
        self.hub.select(self.body())
        with self.assertRaises(ValueError):self.hub.select(self.body('night',request='two'))
    def test_invalid_profile_and_time_never_start(self):
        for body in [self.body('../anything'),self.body('fog',600),self.body('night',450),self.body('congestion',True),self.body(request='')]:
            with self.assertRaises(ValueError):self.hub.select(body)
        self.assertEqual(self.calls,[])
    def test_all_three_profiles_can_be_selected(self):
        self.release.set()
        for profile in ('night','congestion','fog'):
            self.hub.select(self.body(profile,request=profile))
            self.assertEqual(self.hub.state()['performance'],'standard')
            for _ in range(50):
                if self.hub.state()['phase']=='ready':break
                time.sleep(.01)
            self.assertEqual(self.hub.state()['profile'],profile)
        self.assertEqual([x[1] for x in self.calls],['night','congestion','fog'])
    def test_performance_is_validated_and_part_of_idempotency(self):
        with self.assertRaises(ValueError):self.hub.select(dict(self.body(),performance='unbounded'))
        self.assertEqual(self.calls,[])
        body=dict(self.body(),performance='balanced');self.hub.select(body)
        self.assertEqual(self.hub.state()['performance'],'balanced')
        with self.assertRaises(ValueError):self.hub.select(dict(body,performance='standard'))

if __name__=='__main__':unittest.main()
