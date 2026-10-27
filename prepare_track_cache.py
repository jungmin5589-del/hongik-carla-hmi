"""Build the private, pinned actor-selection cache integration."""
import ast,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXPECTED='e3070e0d041c4247fb3fae2efafbbc3ee28a1c74722ea38e1720e05e3b64a1d8'

def patched_source(source):
    if hashlib.sha256(source).hexdigest()!=EXPECTED:
        raise RuntimeError('Inspect changed actor model before applying inference selection cache')
    text=source.decode('utf-8')
    helper='def select_track_parameters'+(ROOT/'track_selection_cache.py').read_text(encoding='utf-8').split('def select_track_parameters',1)[1]
    helper=helper.replace('    import torch\n','    import torch, weakref\n',1)
    anchor='class BaseGaussianModel(BaseModel, ABC):'
    assert text.count(anchor)==1
    text=text.replace(anchor,helper+'\n\n'+anchor,1)
    start=text.index('                gaussian_cuboid_ids = gaussian_nodes_parameters["gaussian_cuboid_ids"]\n',text.index('    def _get_calibrated_tracks('))
    end=text.index('                gaussian_nodes_parameters.update(updated_gaussian_nodes_parameters)\n',start)
    replacement=('                updated_gaussian_nodes_parameters = select_track_parameters(\n'
                 '                    self, gaussian_nodes_parameters, tracks_edit)\n')
    text=text[:start]+replacement+text[end:]
    ast.parse(text);return text

if __name__=='__main__':
    target=ROOT/'vendor/track-cache/gaussians_model.py'
    if target.exists():raise RuntimeError('Back up existing private shim before rebuilding')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(patched_source((ROOT/'validation/runtime-review-20261027/gaussians/gaussians_model.py').read_bytes()),encoding='utf-8')
    print('Created private actor-selection cache shim')
