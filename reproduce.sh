#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: ./reproduce.sh --smoke|--full" >&2
  exit 2
}

if [[ $# -ne 1 ]]; then
  usage
fi

case "$1" in
  --smoke)
    config="configs/v2_smoke.json"
    output="runs/smoke"
    ;;
  --full)
    config="configs/v2_pilot.json"
    output="runs/v2"
    ;;
  *) usage ;;
esac

repo_root="$(cd "$(dirname "$0")" && pwd)"
cd "$repo_root"

if command -v uv >/dev/null 2>&1; then
  uv_bin="$(command -v uv)"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  uv_bin="${HOME}/.local/bin/uv"
else
  echo "uv was not found. Install it from https://docs.astral.sh/uv/ and retry." >&2
  exit 1
fi

if [[ ! -f uv.lock ]]; then
  echo "uv.lock is missing; release reproduction requires a frozen lockfile." >&2
  exit 1
fi

"$uv_bin" sync --frozen --extra dev
"$uv_bin" run --frozen pytest
"$uv_bin" run --frozen python -m quantumopt_v2 run --config "$config" --output "$output"

if [[ "$1" == "--full" ]]; then
  "$uv_bin" run --frozen python -m quantumopt_v2 verify \
    --run "$output" --golden evidence/golden_summary.json
fi

echo "Reproduction completed: $output"
