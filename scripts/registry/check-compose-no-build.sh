#!/usr/bin/env bash
set -euo pipefail

FILES=(
  env/dev/docker-compose.yml
  env/test/docker-compose.yml
  env/prod/docker-compose.yml
  docker-compose.dev.yml
  docker-compose.test.yml
  docker-compose.prod.yml
)

have_rg=true
if ! command -v rg >/dev/null 2>&1; then
  echo "rg not found; falling back to grep" >&2
  have_rg=false
fi

status=0
for file in "${FILES[@]}"; do
  if $have_rg; then
    if rg --quiet '^\s*build:' "$file"; then
      echo "build: directive still present in $file" >&2
      status=1
    fi
  else
    if grep -Eq '^\s*build:' "$file"; then
      echo "build: directive still present in $file" >&2
      status=1
    fi
  fi
  docker compose -f "$file" config >/dev/null
  echo "Verified $file"
  echo ""
done

exit $status
