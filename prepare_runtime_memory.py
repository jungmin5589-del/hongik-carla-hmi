"""Isolate a pinned-runtime loader fix; preserve every checkpoint tensor value."""
import ast
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EXPECTED='c971fc9f2b1d2fc2a43146eae06c4f620168ae81ac0961de0255b2248d11d0da'


def patched_source(source):
    if hashlib.sha256(source).hexdigest()!=EXPECTED:
        raise RuntimeError('Inspect the runtime loader before applying this memory fix.')
    text=source.decode('utf-8')
    old='        checkpoint = torch.load(artifact.checkpoint, weights_only=False)\n'
    if text.count(old)!=1:
        raise RuntimeError('Gaussian loader anchor is missing or ambiguous.')
    new=('        checkpoint = torch.load(artifact.checkpoint, weights_only=False, map_location="cpu")\n'
         '        # Private memory fix: the parsed tensors own their storage; release raw ZIP bytes.\n'
         '        artifact.clear_cache()\n')
    text=text.replace(old,new,1)
    old='        model.to("cuda")\n'
    new=('        # Parameters now own their storage; do not retain checkpoint dictionaries while migrating.\n'
         '        del checkpoint, model_state_dict, upgraded_model_state_dict\n'
         '        if os.environ.get("NUREC_SCENARIO_LOAD") == "essential":\n'
         '            from nre.models.gaussians.gaussians_composite import compact_static_background\n'
         '            compact_static_background(model)\n'
         '        model.to("cuda")\n')
    if text.count(old)!=1:raise RuntimeError('CUDA migration anchor is ambiguous')
    text=text.replace(old,new,1)
    ast.parse(text)
    return text


if __name__=='__main__':
    target=ROOT/'vendor/runtime-memory/render.py'
    if target.exists():raise RuntimeError('Preserve the existing memory compatibility file first.')
    result=patched_source((ROOT/'validation/runtime-review-20261027/render.py').read_bytes())
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(result,encoding='utf-8')
    print('Created private CPU-staged loader:',target)
