#!/usr/bin/env bash
set -euo pipefail

experiment_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$experiment_dir"

uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python src/quantumopt_experiment.py --config config/experiment.json --output-root .
uv run --frozen python src/qa_outputs.py --root . --config config/experiment.json

