#!/usr/bin/env python3
"""Validate the frozen experiment artifacts and fairness invariants."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def verify_checksums(root: Path) -> None:
    checksum_path = root / "checksums.sha256"
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = root / relative
        if not target.is_file():
            raise AssertionError(f"Checksummed file is missing: {relative}")
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"Checksum mismatch: {relative}")


def validate(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    required = [
        "README.md",
        "REPORT.md",
        "NEGATIVE_RESULTS.md",
        "environment.txt",
        "uv.lock",
        "checksums.sha256",
        "raw/candidate_pool.jsonl",
        "raw/loss_schedules.csv",
        "raw/query_log.jsonl",
        "raw/query_pattern_metrics.csv",
        "raw/final_pattern_metrics.csv",
        "results/episode_summary.csv",
        "results/aggregate_metrics.csv",
        "results/statistical_comparisons.csv",
        "results/discovery_gate.json",
        "results/learning_curves.csv",
        "results/pareto_front.csv",
        "figures/heldout_performance.png",
        "figures/learning_curves.png",
        "figures/train_vs_heldout.png",
        "figures/example_search_pareto.png",
    ]
    for relative in required:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"Required non-empty artifact missing: {relative}")

    candidate_rows = load_jsonl(root / "raw/candidate_pool.jsonl")
    query_rows = load_jsonl(root / "raw/query_log.jsonl")
    episode_rows = load_csv(root / "results/episode_summary.csv")
    final_rows = load_csv(root / "raw/final_pattern_metrics.csv")
    expected_candidate_rows = len(config["episode_seeds"]) * int(
        config["candidate_pool_size"]
    )
    if len(candidate_rows) != expected_candidate_rows:
        raise AssertionError(
            f"Candidate row count {len(candidate_rows)} != {expected_candidate_rows}"
        )

    expected_queries = (
        len(config["episode_seeds"])
        * len(config["policies"])
        * int(config["query_budget"])
    )
    if len(query_rows) != expected_queries:
        raise AssertionError(f"Query row count {len(query_rows)} != {expected_queries}")

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in query_rows:
        if row.get("split_visible_to_policy") != "train":
            raise AssertionError("A search query was exposed to a non-training split")
        if any("heldout" in key.lower() for key in row):
            raise AssertionError("Held-out value leaked into query log")
        grouped[(int(row["episode_seed"]), row["policy"])].append(row)

    for seed in config["episode_seeds"]:
        warmup_sequences = []
        for policy in config["policies"]:
            rows = sorted(grouped[(int(seed), policy)], key=lambda row: int(row["step"]))
            if len(rows) != int(config["query_budget"]):
                raise AssertionError(f"Unequal query budget for seed={seed}, policy={policy}")
            if [int(row["step"]) for row in rows] != list(
                range(int(config["query_budget"]))
            ):
                raise AssertionError(f"Non-contiguous steps for seed={seed}, policy={policy}")
            candidate_ids = [row["candidate_id"] for row in rows]
            if len(candidate_ids) != len(set(candidate_ids)):
                raise AssertionError(f"Repeated query for seed={seed}, policy={policy}")
            warmup_sequences.append(
                tuple(candidate_ids[: int(config["warmup_queries"])])
            )
        if len(set(warmup_sequences)) != 1:
            raise AssertionError(f"Warm-up mismatch across policies for seed={seed}")

    episode_counts = Counter(row["policy"] for row in episode_rows)
    for policy in config["policies"]:
        if episode_counts[policy] != len(config["episode_seeds"]):
            raise AssertionError(f"Incomplete episode summary for {policy}")
    for row in episode_rows:
        if int(row["query_budget"]) != int(config["query_budget"]):
            raise AssertionError("Episode summary query budget mismatch")
        if int(row["unique_queries"]) != int(config["query_budget"]):
            raise AssertionError("Episode contains duplicate queries")

    final_splits = {row["split"] for row in final_rows}
    if final_splits != {"train", "heldout"}:
        raise AssertionError(f"Final metrics have unexpected splits: {final_splits}")
    heldout_counts = Counter(
        (row["episode_seed"], row["policy"], row["candidate_id"])
        for row in final_rows
        if row["split"] == "heldout"
    )
    if not heldout_counts or set(heldout_counts.values()) != {
        int(config["heldout_loss_patterns"])
    }:
        raise AssertionError("Held-out pattern count is incomplete or inconsistent")

    gate = json.loads((root / "results/discovery_gate.json").read_text(encoding="utf-8"))
    if not isinstance(gate.get("discovery_gate_passed"), bool):
        raise AssertionError("Discovery gate record lacks a Boolean result")
    verify_checksums(root)
    return {
        "status": "qa_passed",
        "candidate_rows": len(candidate_rows),
        "query_rows": len(query_rows),
        "episode_rows": len(episode_rows),
        "heldout_pattern_rows": sum(heldout_counts.values()),
        "discovery_gate_passed": gate["discovery_gate_passed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    summary = validate(args.root.resolve(), config)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

