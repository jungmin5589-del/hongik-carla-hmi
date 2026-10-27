"""Build a hash-guarded, private native-range side channel for the pinned server."""
import ast,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXPECTED='1174b0ca6bd43c58175163165adb5e0360da0e0d41cdb23675ca1bb2b486f5cc'

def patched_source(source):
    if hashlib.sha256(source).hexdigest()!=EXPECTED:raise RuntimeError('Inspect changed gRPC runtime before patching')
    text=source.decode('utf-8')
    helper=(ROOT/'range_transport.py').read_text(encoding='utf-8').split('def encode_range_hint',1)[1].split('\ndef decode_range_hint',1)[0]
    helper='def encode_range_hint'+helper
    helper+='\n\n'+(ROOT/'inference_outputs.py').read_text(encoding='utf-8').split('def inference_output_overrides',1)[1].join(['def inference_output_overrides',''])
    marker='@dataclass\nclass Backend:'
    assert text.count(marker)==1;text=text.replace(marker,helper+'\n\n'+marker,1)
    old='        self, request: RGBRenderRequest, enable_editing_actors: bool = False\n'
    assert text.count(old)==1;text=text.replace(old,'        self, request: RGBRenderRequest, enable_editing_actors: bool = False, include_range_hint: bool = False, fog_parameters=None\n',1)
    old='''        rendered = self.renderable_model.render_camera_frame_from_ray_bundle(
            ray_bundle,
            actors_snapshot=actors_snapshot,'''
    new='''        rendered = self.renderable_model.render_camera_frame_from_ray_bundle(
            ray_bundle,
            fields=["color_image", "distance_image", "opacity_image"] if include_range_hint or fog_parameters is not None else None,
            actors_snapshot=actors_snapshot,'''
    assert text.count(old)==1;text=text.replace(old,new,1)
    old='        return rendered.color_image, (h, w)\n'
    new='''        self._nurec_native_fog_applied = False
        if fog_parameters is not None:
            fog_color = compose_native_fog(rendered.color_image, rendered.distance_image,
                rendered.opacity_image, fog_parameters[0], fog_parameters[1], ray_bundle.rendering_data.rays[0])
            if fog_color is not None:
                rendered.color_image = fog_color
                self._nurec_native_fog_applied = True
        self._nurec_range_hint = encode_range_hint(rendered.distance_image, rendered.opacity_image,
            request.frame_start_us) if include_range_hint and not self._nurec_native_fog_applied else None
        return rendered.color_image, (h, w)
'''
    assert text.count(old)==1;text=text.replace(old,new,1)
    old='                raster_f32, img_size = backend.render_camera_request(request, self.enable_editing_actors)\n'
    new='''                include_range_hint = any(m.key == "x-nurec-range" and m.value == "1"
                    for m in context.invocation_metadata())
                fog_parameters = None
                for m in context.invocation_metadata():
                    if m.key == "x-nurec-fog":
                        import json, math
                        try:
                            beta,seconds = json.loads(m.value)
                            beta,seconds = float(beta),float(seconds)
                            if math.isfinite(beta) and math.isfinite(seconds) and 0.<beta<=.3 and 0.<=seconds<=3600.:
                                fog_parameters = (beta,seconds)
                        except (ValueError,TypeError):
                            pass
                raster_f32, img_size = backend.render_camera_request(request, self.enable_editing_actors,
                    include_range_hint=include_range_hint, fog_parameters=fog_parameters)
                if backend._nurec_native_fog_applied:
                    context.set_trailing_metadata((("nurec-fog", "1"),))
                elif include_range_hint and backend._nurec_range_hint is not None:
                    context.set_trailing_metadata((("nurec-range-bin", backend._nurec_range_hint),))
'''
    assert text.count(old)==1;text=text.replace(old,new,1)
    old='            if renderer == Backend.RendererType.GSPLAT:\n'
    new=('            if renderer == Backend.RendererType.DEFAULT:\n'
         '                config_overrides = inference_output_overrides()\n'
         '            elif renderer == Backend.RendererType.GSPLAT:\n')
    assert text.count(old)==1;text=text.replace(old,new,1)
    text=text.replace('        log.info("render_rgb")','        log.debug("render_rgb")',1)
    old='            if not inserted:\n                raise RuntimeError(f"Failed to insert track_id=\'{track_id}\' with asset_id=\'{asset_id}\'")\n'
    new=old+"            # Asset edits are serialized; release only unused CUDA allocator blocks.\n            del asset, nre_cuboid_track\n            torch.cuda.empty_cache()\n"
    assert text.count(old)==1;text=text.replace(old,new,1)
    ast.parse(text);return text

if __name__=='__main__':
    target=ROOT/'vendor/native-range/serve.py'
    if target.exists():raise RuntimeError('Preserve the existing native range shim before rebuilding')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(patched_source((ROOT/'validation/runtime-review-20261027/serve.py').read_bytes()),encoding='utf-8')
    print('Created same-render native range shim')
