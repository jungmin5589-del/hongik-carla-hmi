import math,unittest
from types import SimpleNamespace as NS
import numpy as np
from native_alignment import route_atlas,start_alignment,steering_geometry,route_index,ego_lane
from native_carla_route import steering,curve_speed_limit

class Lane:
    def __init__(self,s,y,kind='Driving',lane=-1):
        self.s=s;self.road_id=1;self.section_id=0;self.lane_id=lane;self.id=(s,lane);self.lane_type=kind;self.lane_width=3.5
        self.transform=NS(location=NS(x=s,y=y),rotation=NS(yaw=0.));self.left=self.right=None
    def get_left_lane(self):return self.left
    def get_right_lane(self):return self.right

class Straight:
    length=1000.;arc=np.arange(0,1001,1.)
    def sample(self,s,offset=0.):return np.array([s,offset,0.]),0.

def actor(x,y,yaw=0.,speed=0.):
    return NS(id=1,get_transform=lambda:NS(location=NS(x=x,y=y),rotation=NS(yaw=yaw)),get_velocity=lambda:NS(length=lambda:speed))

class AlignmentTests(unittest.TestCase):
    def test_parking_is_a_real_separate_lane_in_atlas(self):
        points=[]
        for s in (0.,3.,6.):
            driving=Lane(s,0.);parking=Lane(s,3.5,'Parking',-2);driving.right=parking;parking.left=driving;points.append(driving)
        result=route_atlas(NS(waypoints=points),'Town03')
        parking=next(r for r in result['roads'] if r['kind']=='Parking')
        self.assertEqual(parking['points'],[[0.,3.5],[3.,3.5],[6.,3.5]])
        self.assertEqual(result['coordinate_frame'],'carla_xy')
    def test_atlas_does_not_draw_fake_road_across_a_gap(self):
        points=[Lane(s,0.) for s in (0.,3.,50.,53.)]
        self.assertEqual(len(route_atlas(NS(waypoints=points),'Town03')['roads']),2)
    def test_departure_checks_assigned_offset_not_driving_centerline(self):
        item=dict(actor=actor(5.,3.5),role='ego',s=5.,offset=3.5)
        self.assertTrue(start_alignment(Straight(),[item])['ready'])
        item['actor']=actor(5.,3.5,180.)
        self.assertFalse(start_alignment(Straight(),[item])['ready'])
        item['actor']=actor(8.,3.5)
        self.assertFalse(start_alignment(Straight(),[item])['ready'])
    def test_wheel_world_centimetres_are_rotation_invariant(self):
        a=actor(100.,200.,90.)
        wheels=[NS(position=NS(x=10000.+right,y=20000.+forward),max_steer_angle=angle) for forward,right,angle in ((150,-80,70),(150,80,70),(-150,-80,0),(-150,80,0))]
        a.get_physics_control=lambda:NS(wheels=wheels)
        g=steering_geometry(a)
        self.assertAlmostEqual(g['wheelbase'],3.);self.assertAlmostEqual(g['rear_offset'],-1.5);self.assertAlmostEqual(g['max_steer'],math.radians(70))
    def test_circle_speed_and_straight_preference(self):
        class Circle:
            def sample(self,s,offset=0.):
                radius=50.-offset;a=s/50.;return np.array([radius*math.sin(a),radius*(1-math.cos(a)),0.]),a
        self.assertAlmostEqual(curve_speed_limit(Straight(),100.,0.,90.),90.)
        self.assertLess(curve_speed_limit(Circle(),100.,0.,90.),45.)
    def test_physical_wheelbase_and_angle_change_normalized_steering(self):
        tr=actor(0.,1.).get_transform()
        car=steering(Straight(),0.,0.,tr,8.,dict(wheelbase=3.,rear_offset=-1.5,max_steer=1.2))
        truck=steering(Straight(),0.,0.,tr,8.,dict(wheelbase=6.,rear_offset=-1.5,max_steer=1.2))
        self.assertLess(car,0.);self.assertGreater(abs(truck),abs(car))
        full=dict(wheelbase=3.,rear_offset=-1.5,max_steer=1.2)
        reduced=dict(full,steering_curve=[(0.,1.),(36.,.5)])
        self.assertAlmostEqual(steering(Straight(),0.,0.,tr,10.,reduced),2*steering(Straight(),0.,0.,tr,10.,full))
    def test_route_index_follows_actual_arc_including_bounded_endpoint(self):
        r=Straight();r.arc=np.array([0.,1.,2.,8.,9.,10.,20.])
        self.assertEqual(route_index(r,9.),1)
        r.cross_s=15.;self.assertEqual(route_index(r,2000.),2)
    def test_old_navigation_cannot_start_the_new_scene(self):
        import threading
        from native_carla import NativeBridge
        b=NativeBridge.__new__(NativeBridge);b.lock=threading.RLock();b.scenario=NS(session='new',elapsed=2.,completed=False)
        b.state=dict(phase='live');b.command=dict(mode='paused')
        with self.assertRaises(ValueError):b.control(dict(mode='auto',session_id='old'))
        self.assertEqual(b.command['mode'],'paused')
        self.assertTrue(b.control(dict(mode='paused',session_id='new'))['accepted'])
    def test_lane_display_uses_current_local_geometry_after_a_lane_change(self):
        lanes=[dict(points=[dict(forward_m=0.,right_m=offset)]) for offset in (-3.5,0.,3.5,7.)]
        self.assertEqual(ego_lane(lanes),(2,4))
        for lane in lanes:lane['points'][0]['right_m']+=3.5
        self.assertEqual(ego_lane(lanes),(1,4))
        lanes.append(dict(kind='Parking',points=[dict(forward_m=0.,right_m=0.)]))
        self.assertEqual(ego_lane(lanes),(1,4))

if __name__=='__main__':unittest.main()


class MapCacheTests(unittest.TestCase):
    def test_prepared_map_avoids_world_rpc_during_requests(self):
        from native_alignment import cached_map
        from types import SimpleNamespace
        from unittest.mock import Mock
        prepared=object();world=SimpleNamespace(get_map=Mock(side_effect=AssertionError('Unexpected map RPC')))
        self.assertIs(cached_map(SimpleNamespace(road_map=prepared,world=world)),prepared)
