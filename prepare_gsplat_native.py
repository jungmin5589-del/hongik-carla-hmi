"""Private, pinned-runtime native camera projection test; no weight changes."""
import ast
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXPECTED='1174b0ca6bd43c58175163165adb5e0360da0e0d41cdb23675ca1bb2b486f5cc'


def patched_source(source):
    if hashlib.sha256(source).hexdigest()!=EXPECTED:
        raise RuntimeError('Inspect a changed server before enabling the native-camera candidate.')
    text=source.decode('utf-8')
    old='config_overrides = ("model.renderer.name=3dgut-gsplat",)'
    if text.count(old)!=1:raise RuntimeError('GSplat selection anchor is ambiguous.')
    text=text.replace(old,'config_overrides = ("model.renderer.name=3dgut-gsplat", "model.renderer.use_rays=False")',1)
    old='        return {key: stringify_value(value) for key, value in raw_config_dict.items()}'
    if text.count(old)!=1:raise RuntimeError('Server config anchor is ambiguous.')
    new=('        result = {key: stringify_value(value) for key, value in raw_config_dict.items()}\n'
         '        if result.get("renderer") == "gsplat":\n'
         '            result["nurec_private_camera_mode"] = "native"\n'
         '        return result')
    text=text.replace(old,new,1)
    ast.parse(text)
    return text


if __name__=='__main__':
    target=ROOT/'vendor/gsplat-native/serve.py'
    if target.exists():raise RuntimeError('Preserve the existing camera compatibility file first.')
    result=patched_source((ROOT/'validation/runtime-review-20261027/serve.py').read_bytes())
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(result,encoding='utf-8')
    print('Created native-camera GSplat candidate:',target)
