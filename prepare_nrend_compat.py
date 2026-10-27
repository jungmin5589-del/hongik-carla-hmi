"""Build an isolated patch only for the inspected, pinned official runtime file."""
import ast
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EXPECTED='1174b0ca6bd43c58175163165adb5e0360da0e0d41cdb23675ca1bb2b486f5cc'


def patched_source(source):
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise RuntimeError('Runtime source hash differs; inspect it before building a compatibility patch.')
    text=source.decode('utf-8')
    edits=[
        ('from nre.grpc.scene_cache import SceneCache',
         'from nurec_compat import refresh_nrend\nfrom nre.grpc.scene_cache import SceneCache'),
        ('                self.insert_assets(insert_assets)\n        except Exception:',
         '                self.insert_assets(insert_assets)\n            refresh_nrend(self.renderable_model)\n        except Exception:'),
        ('            self.renderable_model.restore_training_parameters()\n            raise',
         '            self.renderable_model.restore_training_parameters()\n            refresh_nrend(self.renderable_model)\n            raise'),
        ('        self.renderable_model.restore_training_parameters()\n\n    @with_render_lock()',
         '        self.renderable_model.restore_training_parameters()\n        refresh_nrend(self.renderable_model)\n\n    @with_render_lock()'),
    ]
    for old,new in edits:
        if text.count(old)!=1:
            raise RuntimeError('Runtime compatibility anchor is missing or ambiguous.')
        text=text.replace(old,new,1)
    ast.parse(text)
    return text


if __name__=='__main__':
    source=ROOT/'validation/runtime-review-20261027/serve.py'
    target=ROOT/'vendor/nrend-asset-compat/serve.py'
    if target.exists():
        raise RuntimeError('Compatibility build already exists; preserve it before rebuilding.')
    result=patched_source(source.read_bytes())
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(result,encoding='utf-8')
    print('Created private NRend compatibility file:',target)
