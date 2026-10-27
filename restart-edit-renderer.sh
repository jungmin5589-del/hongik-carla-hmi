#!/usr/bin/env bash
set -euo pipefail
name=nurec-live-20261019
expected=nvcr.io/nvidia/nre/nre-ga@sha256:97f43e7130c5636ce3e80ea3184d97f56a87fdd989b05cce42230881dbdea284
if docker container inspect "$name" >/dev/null 2>&1; then
  actual=$(docker inspect --format '{{.Config.Image}}' "$name")
  label=$(docker inspect --format '{{index .Config.Labels "codex.nurec.trial"}}' "$name")
  [[ "$actual" = "$expected" && "$label" = 20261019 ]] || { printf 'Foreign container; stopping.\n' >&2; exit 1; }
  docker stop --timeout 10 "$name"
  for ((attempt=0;attempt<200;attempt++)); do
    docker container inspect "$name" >/dev/null 2>&1 || break
    sleep .1
  done
fi
exec bash /mnt/d/CARLA-Maps/NuRec-OneScene-20261018/live/serve-live.sh
