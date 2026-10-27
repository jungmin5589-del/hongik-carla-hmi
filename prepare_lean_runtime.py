"""Build a source-hash guarded inference-layer selector for the pinned runtime."""
import ast
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXPECTED='df0aa94a2f15ec4a8302a6ba21f067b111992a2e4239979ebb09d2777f34f888'


def patched_source(source):
    if hashlib.sha256(source).hexdigest()!=EXPECTED:
        raise RuntimeError('Inspect the changed Gaussian runtime before applying lean inference.')
    text=source.decode('utf-8')
    helper=(ROOT/'lean_runtime.py').read_text(encoding='utf-8').split('def select_render_nodes',1)[1]
    helper='def select_render_nodes'+helper
    anchor='log = logging.getLogger(__name__)\n'
    if text.count(anchor)!=1:raise RuntimeError('Helper placement anchor is ambiguous.')
    text=text.replace(anchor,anchor+'\n\n'+helper+'\n',1)
    old='        all_node_ids = list(self.gaussians_nodes.keys())\n'
    if text.count(old)!=1:raise RuntimeError('Layer selection anchor is missing or ambiguous.')
    new=('        if not is_training_batch:\n'
         '            compact_static_background(self)\n'
         '        if not is_training_batch and edited_cuboid_tracks is not None:\n'
         '            candidates = gaussian_nodes if gaussian_nodes is not None else self.get_gaussians_node_ids()\n'
         '            gaussian_nodes = select_render_nodes(self, candidates, edited_cuboid_tracks)\n\n'+old)
    text=text.replace(old,new,1);ast.parse(text)
    return text


if __name__=='__main__':
    target=ROOT/'vendor/lean-runtime/gaussians_composite.py'
    if target.exists():raise RuntimeError('Preserve an existing lean runtime before rebuilding it.')
    result=patched_source((ROOT/'validation/runtime-review-20261027/gaussians/gaussians_composite.py').read_bytes())
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(result,encoding='utf-8')
    print('Created isolated lean inference runtime:',target)
