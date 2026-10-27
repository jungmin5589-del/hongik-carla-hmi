import unittest
from types import SimpleNamespace as NS
from lean_runtime import select_render_nodes
from scenario_workload import required_proxy_ids
from prepare_lean_runtime import patched_source


class WorkloadTests(unittest.TestCase):
    def trial(self,**values):
        return NS(**dict(dict(enabled=True,TRACK_ID='108',SUPPRESS_OTHER_TRAFFIC=True),**values))

    def test_normal_trial_keeps_its_stimulus_and_full_or_free_mode_keeps_everything(self):
        trial=self.trial()
        self.assertEqual(required_proxy_ids(trial),{'108'})
        self.assertIsNone(required_proxy_ids(trial,'full'))
        self.assertIsNone(required_proxy_ids(trial,include_all=True))
        self.assertIsNone(required_proxy_ids(self.trial(enabled=False)))
        self.assertIsNone(required_proxy_ids(self.trial(OVERTAKE_TRIAL=True)))

    def test_highway_keeps_all_fast_cars_and_all_three_large_vehicles(self):
        ids=['lead','truck1','truck2','bus']+[f'fast{i}' for i in range(12)]
        trial=self.trial(config={'vehicles':{key:{} for key in ids}})
        self.assertEqual(required_proxy_ids(trial),set(ids))
        self.assertEqual(len(required_proxy_ids(trial)),16)

    def model(self):
        return NS(gaussians_nodes={
            'background':NS(),
            'parked':NS(is_static=True,cuboid_tracks=NS(tracks_id=['static'])),
            'cars':NS(is_static=False,cuboid_tracks=NS(tracks_id=['108','truck'])),
            'pedestrians':NS(is_static=False,cuboid_tracks=NS(tracks_id=['person']))})

    def test_only_unrequested_dynamic_group_is_skipped(self):
        model=self.model();keys=list(model.gaussians_nodes)
        selected=select_render_nodes(model,keys,NS(tracks_id=['108']))
        self.assertEqual(selected,['background','parked','cars'])
        self.assertEqual(list(model.gaussians_nodes),keys)

    def test_changed_actor_requests_reactivate_the_required_group(self):
        model=self.model();keys=list(model.gaussians_nodes)
        select_render_nodes(model,keys,NS(tracks_id=['108']))
        self.assertEqual(select_render_nodes(model,keys,NS(tracks_id=['person'])),['background','parked','pedestrians'])
        self.assertEqual(select_render_nodes(model,['cars'],NS(tracks_id=['truck'])),['cars'])

    def test_empty_actor_selection_preserves_static_scenery_and_unknown_runtime_is_rejected(self):
        model=self.model()
        self.assertEqual(select_render_nodes(model,list(model.gaussians_nodes),NS(tracks_id=[])),['background','parked'])
        with self.assertRaises(RuntimeError):patched_source(b'unknown runtime')


if __name__=='__main__':unittest.main()
