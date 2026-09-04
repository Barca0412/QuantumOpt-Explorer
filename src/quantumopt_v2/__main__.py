"""Command-line interface for QuantumOpt-Explorer V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from .runner import load_config, run_experiment, verify_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m quantumopt_v2")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run a frozen V2 experiment")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify", help="verify a run against an external golden file")
    verify.add_argument("--run", type=Path, required=True)
    verify.add_argument("--golden", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    started = time.perf_counter()
    if args.command == "run":
        result = run_experiment(load_config(args.config), args.output)
        message = {
            "status": "completed",
            "output": result["output"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "config_hash": result["manifest"]["config_hash"],
            "protocol_hash": result["manifest"]["protocol_hash"],
            "quantitative_signal_pass": result["gate"]["quantitative_signal_pass"],
            "discovery_claim_pass": result["gate"]["discovery_claim_pass"],
        }
    else:
        message = verify_run(args.run, args.golden)
        message["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    print(json.dumps(message, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
