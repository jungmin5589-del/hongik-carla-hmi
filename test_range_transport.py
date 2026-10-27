import unittest,struct,zlib,io,ast
import numpy as np
from PIL import Image
from range_transport import decode_range_hint
from fog_effect import FogEffect
from prepare_native_range import patched_source,ROOT

class NativeRangeTests(unittest.TestCase):
    def payload(self,value,stamp=123):return struct.pack('<4sHHQ',b'NRD1',240,135,stamp)+zlib.compress(value.astype('<f2').tobytes())
    def test_same_request_grid_preserves_range_and_rejects_cross_frame_or_corrupt_data(self):
        value=np.linspace(.1,500,240*135,dtype=np.float32).reshape(135,240)
        payload=self.payload(value)
        np.testing.assert_array_equal(decode_range_hint(payload,123),value.astype(np.float16).astype(np.float32))
        for bad,stamp in [(payload,124),(b'bad',123),(payload[:-3],123),(payload+b'tail',123),(self.payload(np.full((135,240),np.nan)),123)]:
            self.assertIsNone(decode_range_hint(bad,stamp))
    def test_native_hint_avoids_point_cloud_work_and_clear_stage_is_unchanged(self):
        f=FogEffect()
        def forbidden(*args,**kwargs):raise AssertionError('Point cloud fallback must not run for a valid native range')
        f.ranges=forbidden
        stream=io.BytesIO();Image.new('RGB',(320,180),(40,60,80)).save(stream,format='JPEG');jpeg=stream.getvalue()
        ranges=np.full((135,240),20.,dtype=np.float32)
        result,meta=f.apply(jpeg,None,None,dict(fog=dict(beta=.05,stage='thick'),elapsed_s=180),native_ranges=ranges)
        self.assertEqual(meta['range_source'],'native_same_frame');self.assertEqual(meta['points'],0)
        self.assertFalse(hasattr(f,'points'));self.assertEqual(Image.open(io.BytesIO(result)).size,(320,180))
        clear,_=f.apply(jpeg,None,None,dict(fog=dict(beta=0.)),native_ranges=ranges)
        self.assertEqual(clear,jpeg)
    def test_pinned_server_patch_keeps_backend_dataclass_and_rejects_unknown_source(self):
        source=(ROOT/'validation/runtime-review-20261027/serve.py').read_bytes()
        tree=ast.parse(patched_source(source));backend=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Backend')
        self.assertTrue(any(isinstance(n,ast.Name) and n.id=='dataclass' for n in backend.decorator_list))
        with self.assertRaises(RuntimeError):patched_source(b'unknown runtime')

if __name__=='__main__':unittest.main()
