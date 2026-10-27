#!/usr/bin/env bash
# One authorized scene; pinned runtime; localhost only; no privileged container.
set -euo pipefail
root=/mnt/d/CARLA-Maps/NuRec-OneScene-20261018
image=nvcr.io/nvidia/nre/nre-ga@sha256:97f43e7130c5636ce3e80ea3184d97f56a87fdd989b05cce42230881dbdea284
container=nurec-live-20261019
artifact=/data/sample_set/26.04_release/00040136-e651-4abd-991d-0655ccda9430/00040136-e651-4abd-991d-0655ccda9430.usdz
profile=${1:-night}
backend=${2:-trained}
workload=${3:-full}
case "$backend" in
  trained) renderer_args=(--renderer default) ;;
  nrend) renderer_args=(--renderer nrend) ;;
  gsplat) renderer_args=(--renderer gsplat) ;;
  gsplat-native) renderer_args=(--renderer gsplat) ;;
  *) printf 'Unknown rendering backend\n' >&2; exit 2 ;;
esac
compat_mounts=()
runtime=/app/internal/scripts/pycena/runtime/pycena_nrm_full.runfiles/_main
# Native NRend keeps its own compiler cache beside renderer.py. Preserve it
# separately for this exact image and compute capability across --rm sessions.
gpu_arch=$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -n1 | tr -cd '0-9') || gpu_arch=""
if [[ "$gpu_arch" =~ ^[0-9]{2,3}$ ]]; then
  ptx_cache="$root/cache/nrend-ptx/97f43e7130c5636ce3e80ea3184d97f56a87fdd989b05cce42230881dbdea284-sm$gpu_arch"
  mkdir -p "$ptx_cache"
  compat_mounts+=(--mount "type=bind,src=$ptx_cache,dst=$runtime/libs/nrend/ptx_cache")
else
  printf 'Native kernel cache disabled: GPU architecture unavailable.\n' >&2
fi
[[ -f "$root/live/vendor/runtime-memory/render.py" ]] || exit 3
compat_mounts+=(--mount "type=bind,src=$root/live/vendor/runtime-memory/render.py,dst=$runtime/nre/render/render.py,readonly")
case "$workload" in
  full) ;;
  essential)
    [[ -f "$root/live/vendor/lean-runtime/gaussians_composite.py" && -f "$root/live/lean_runtime.py" ]] || exit 3
    lean_source="$root/live/vendor/lean-runtime/gaussians_composite.py"
    if [[ "$profile" == congestion && "$backend" == trained && -f "$root/live/static-view-cache.enabled" ]]; then
      lean_source="$root/live/vendor/static-view/gaussians_composite.py"
      [[ -f "$lean_source" ]] || exit 3
    fi
    compat_mounts+=(--mount "type=bind,src=$lean_source,dst=$runtime/nre/models/gaussians/gaussians_composite.py,readonly")
    compat_mounts+=(--mount "type=bind,src=$root/live/lean_runtime.py,dst=$runtime/lean_runtime.py,readonly")
    ;;
  *) exit 2 ;;
esac
if [[ "$backend" == trained && "$workload" == essential ]]; then
  [[ -f "$root/live/vendor/native-range/serve.py" ]] || exit 3
  compat_mounts+=(--mount "type=bind,src=$root/live/vendor/native-range/serve.py,dst=$runtime/nre/grpc/serve.py,readonly")
fi
if [[ "$backend" == nrend ]]; then
  [[ -f "$root/live/vendor/nrend-asset-compat/serve.py" && -f "$root/live/nurec_compat.py" ]] || exit 3
  compat_mounts+=(--mount "type=bind,src=$root/live/vendor/nrend-asset-compat/serve.py,dst=$runtime/nre/grpc/serve.py,readonly")
  compat_mounts+=(--mount "type=bind,src=$root/live/nurec_compat.py,dst=$runtime/nurec_compat.py,readonly")
fi
if [[ "$backend" == gsplat-native ]]; then
  [[ -f "$root/live/vendor/gsplat-native/serve.py" ]] || exit 3
  compat_mounts+=(--mount "type=bind,src=$root/live/vendor/gsplat-native/serve.py,dst=$runtime/nre/grpc/serve.py,readonly")
fi
case "$profile" in
  night) ;;
  fog) artifact=/data/sample_set/26.04_release/8ba55c12-2cd3-4dce-aadd-c17dbb19642f/8ba55c12-2cd3-4dce-aadd-c17dbb19642f.usdz ;;
  congestion) artifact=/data/sample_set/26.04_release/200c6367-6372-437d-949b-620851624628/200c6367-6372-437d-949b-620851624628.usdz ;;
  *) printf 'Unknown profile\n' >&2; exit 2 ;;
esac
stamp=$(date +%Y%m%d-%H%M%S)
log="$root/live/grpc-server-$stamp.log"
retain_aux=0
[[ ! -f "$root/live/retain-training-outputs.enabled" ]] || retain_aux=1
timing_args=()
if [[ -f "$root/live/profile-renderer.enabled" ]]; then
  timing_args=(--enable-timing --timing-verbosity BASIC --timing-logfile "/trial-cache/pipeline-timing-$stamp.log")
fi
if docker container inspect "$container" >/dev/null 2>&1; then
  printf 'This trial container already exists; do not replace a running session.\n' >&2
  exit 1
fi
cleanup() {
  docker stop --timeout 10 "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
printf '%s\n' "$log"
docker run --rm --name "$container" --label codex.nurec.trial=20261019 --gpus all --shm-size=64g \
  "${compat_mounts[@]}" \
  -p 127.0.0.1:46435:46435 \
  --mount "type=bind,src=$root/source,dst=/data,readonly" \
  --mount "type=bind,src=$root/cache,dst=/trial-cache" \
  --env XDG_CACHE_HOME=/trial-cache \
  --env NUREC_RETAIN_TRAINING_OUTPUTS="$retain_aux" \
  --env NUREC_SCENARIO_LOAD="$workload" \
  --env TORCH_EXTENSIONS_DIR=/trial-cache/torch_extensions \
  --env CUDA_CACHE_PATH=/trial-cache/cuda \
  --env TORCHINDUCTOR_COMPILE_THREADS=1 --env OMP_NUM_THREADS=2 --env OPENBLAS_NUM_THREADS=1 \
  "$image" -- serve-grpc --artifact-glob "$artifact" \
  --host 0.0.0.0 --port 46435 --cache-size 1 "${renderer_args[@]}" --enable-editing-actors \
  --test-scenes-are-valid "${timing_args[@]}" > "$log" 2>&1
