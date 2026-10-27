import ast,unittest,os
from unittest.mock import patch
from pathlib import Path
from inference_outputs import inference_output_overrides
from prepare_native_range import patched_source,ROOT

class OutputTests(unittest.TestCase):
    def test_only_unused_training_outputs_are_overridden(self):
        expected={'model.renderer.outputs.camera.enable_ray_gradients','model.renderer.outputs.scene.enable_cumulated_weights','model.renderer.outputs.scene.enable_visibility'}
        items=inference_output_overrides();self.assertEqual({item.split('=')[0] for item in items},expected)
        self.assertTrue(all(item.endswith('=false') for item in items))
    def test_baseline_can_retain_the_original_outputs(self):
        with patch.dict(os.environ,{"NUREC_RETAIN_TRAINING_OUTPUTS":"1"}):
            self.assertEqual(inference_output_overrides(),())
    def test_patched_backend_uses_overrides_only_for_the_default_renderer(self):
        source=patched_source((ROOT/'validation/runtime-review-20261027/serve.py').read_bytes())
        tree=ast.parse(source)
        backend=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Backend')
        method=next(n for n in backend.body if isinstance(n,ast.FunctionDef) and n.name=='from_artifact')
        test=next(n for n in ast.walk(method) if isinstance(n,ast.If) and 'RendererType.DEFAULT' in ast.unparse(n.test))
        self.assertIn('config_overrides = inference_output_overrides()',ast.unparse(test))
        self.assertIn('Backend.RendererType.GSPLAT',ast.unparse(test))

if __name__=='__main__':unittest.main()
