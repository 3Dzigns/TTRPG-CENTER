#!/usr/bin/env bash
set -euo pipefail

# container-with-2 friendly wrapper for immutable image builds
# 1. Verifies docker availability
# 2. Builds images via scripts/registry/build-images.py
# 3. Confirms docker-compose configs are buildless

: "${TTRPG_REGISTRY:=ghcr.io/ttrpg-center}"
: "${TTRPG_ENVIRONMENTS:=dev test prod}"
: "${TTRPG_PUSH:=true}"

command -v docker >/dev/null 2>&1 || { echo "docker cli is required" >&2; exit 1; }

args=("--registry" "$TTRPG_REGISTRY")
for env in $TTRPG_ENVIRONMENTS; do
  args+=("--env" "$env")
fi

if [[ "$TTRPG_PUSH" == "false" ]]; then
  args+=("--no-push")
fi

python scripts/registry/build-images.py "${args[@]}"

scripts/registry/check-compose-no-build.sh
