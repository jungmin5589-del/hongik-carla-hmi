import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from nurec_compat import refresh_nrend
from prepare_nrend_compat import patched_source


class RefreshTests(unittest.TestCase):
    def renderable(self,ids):
        model=SimpleNamespace(_nrend_renderer=object(),get_updated_cuboid_tracks=lambda:SimpleNamespace(tracks_id=ids))
        model.has_nrend=lambda:model._nrend_renderer is not None
        def setup(track_ids):
            self.assertIsNone(model._nrend_renderer)
            model.registered=list(track_ids);model._nrend_renderer=object()
        model.setup_nrend=setup
        return SimpleNamespace(_model=model,_nrend=SimpleNamespace(tracks=SimpleNamespace(tracks_id=['original'])))

    def test_insert_and_restore_refresh_both_track_list_and_gpu_data(self):
        for ids in (['original','truck','fast_car'],['original']):
            value=self.renderable(ids)
            with patch.dict(sys.modules,{'torch':SimpleNamespace(cuda=SimpleNamespace(empty_cache=Mock()))}):
                self.assertTrue(refresh_nrend(value))
            self.assertEqual(value._nrend.tracks.tracks_id,ids)
            self.assertEqual(value._model.registered,ids)

    def test_non_nrend_backend_is_untouched(self):
        value=self.renderable(['original']);value._model._nrend_renderer=None
        self.assertFalse(refresh_nrend(value))
        self.assertEqual(value._nrend.tracks.tracks_id,['original'])

    def test_duplicate_ids_and_changed_runtime_are_rejected(self):
        with self.assertRaises(RuntimeError):refresh_nrend(self.renderable(['same','same']))
        with self.assertRaises(RuntimeError):patched_source(b'unknown runtime')

    def test_failed_gpu_rebuild_cannot_publish_a_stale_track_list(self):
        value=self.renderable(['original','truck']);value._model.setup_nrend=lambda **kwargs:None
        with patch.dict(sys.modules,{'torch':SimpleNamespace(cuda=SimpleNamespace(empty_cache=Mock()))}):
            with self.assertRaises(RuntimeError):refresh_nrend(value)
        self.assertEqual(value._nrend.tracks.tracks_id,['original'])


if __name__=='__main__':unittest.main()
