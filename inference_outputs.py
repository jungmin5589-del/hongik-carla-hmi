"""Inference outputs used by RGB/range HMI, independent of visual settings."""


def inference_output_overrides():
    import os
    if os.environ.get("NUREC_RETAIN_TRAINING_OUTPUTS")=="1":return ()
    # These are training/diagnostic products, not RGB, range, opacity or culling.
    return (
        'model.renderer.outputs.camera.enable_ray_gradients=false',
        'model.renderer.outputs.scene.enable_cumulated_weights=false',
        'model.renderer.outputs.scene.enable_visibility=false',
    )
