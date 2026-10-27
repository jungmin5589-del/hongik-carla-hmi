"""Optional private view-selection experiment; keep default runtime separate."""
import ast
from pathlib import Path
from prepare_lean_runtime import patched_source
ROOT=Path(__file__).resolve().parent

def view_source():
    source=ROOT/'validation/runtime-review-20261027/gaussians/gaussians_composite.py'
    text=patched_source(source.read_bytes())
    helper='def background_view_parameters'+(ROOT/'background_view_cache.py').read_text(encoding='utf-8').split('def background_view_parameters',1)[1]
    helper=helper.replace('    import torch, os\n','    import torch, os, math, weakref\n',1)
    anchor='log = logging.getLogger(__name__)\n'
    assert text.count(anchor)==1;text=text.replace(anchor,anchor+'\n\n'+helper+'\n',1)
    old='                params = gaussians.get_parameters()\n'
    new=old+('                if node_id in ("background", "road") and not is_training_batch:\n'
             '                    params = background_view_parameters(gaussians, params, rendering_data)\n')
    assert text.count(old)==1;text=text.replace(old,new,1);ast.parse(text);return text

if __name__=='__main__':
    target=ROOT/'vendor/static-view/gaussians_composite.py'
    if target.exists():raise RuntimeError('Back up the existing experiment before rebuilding')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(view_source(),encoding='utf-8')
    print('Created isolated static-view experiment; default runtime unchanged')
