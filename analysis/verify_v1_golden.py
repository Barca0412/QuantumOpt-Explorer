#!/usr/bin/env python3
"""Semantically verify the frozen V1 experiment against a golden fixture.

This verifier recomputes counts, paired effects, aggregate means, query fairness,
loss-schedule shape, phenotype uniqueness, and the discovery decision.  Checksums
alone are intentionally insufficient.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_gzip_jsonl(path: Path) -> List[Dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_gzip_csv(path: Path) -> List[Dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_close(actual: float, expected: float, tolerance: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(
            f"{label}: actual {actual:.17g} != expected {expected:.17g} "
            f"within absolute tolerance {tolerance:g}"
        )


def canonical_phenotype(design: Dict[str, Any]) -> str:
    depth = int(design["depth"])
    layers = []
    for layer in design["layers"][:depth]:
        pattern = int(layer["pattern"])
        theta_count = 2 if pattern == 0 else 1
        layers.append(
            (
                pattern,
                tuple(int(value) for value in layer["theta_indices"][:theta_count]),
                tuple(int(value) for value in layer["phase_indices"]),
            )
        )
    return json.dumps((depth, layers), separators=(",", ":"))


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=repository / "archive" / "v1" / "reproducibility",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=repository / "evidence" / "v1_golden_summary.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive = args.archive_root.resolve()
    package_root = archive.parent
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    tolerance = float(fixture["absolute_tolerance"])
    config = json.loads((archive / "config" / "experiment.json").read_text(encoding="utf-8"))

    for key, expected in fixture["configuration"].items():
        require(config[key] == expected, f"configuration mismatch for {key}")

    episode_rows = read_csv(archive / "results" / "episode_summary.csv")
    aggregate_rows = read_csv(archive / "results" / "aggregate_metrics.csv")
    comparison_rows = read_csv(archive / "results" / "statistical_comparisons.csv")
    gate = json.loads((archive / "results" / "discovery_gate.json").read_text(encoding="utf-8"))
    candidate_rows = read_jsonl(archive / "raw" / "candidate_pool.jsonl")
    query_rows = read_jsonl(archive / "raw" / "query_log.jsonl")
    query_pattern_rows = read_csv(archive / "raw" / "query_pattern_metrics.csv")
    final_pattern_rows = read_csv(archive / "raw" / "final_pattern_metrics.csv")
    loss_rows = read_csv(archive / "raw" / "loss_schedules.csv")
    learning_rows = read_csv(archive / "results" / "learning_curves.csv")
    pareto_rows = read_csv(archive / "results" / "pareto_front.csv")

    semantic_counts = {
        "candidate_rows": len(candidate_rows),
        "query_rows": len(query_rows),
        "query_pattern_rows": len(query_pattern_rows),
        "final_pattern_rows": len(final_pattern_rows),
        "loss_schedule_rows": len(loss_rows),
        "episode_rows": len(episode_rows),
        "learning_curve_rows": len(learning_rows),
        "pareto_rows": len(pareto_rows),
        "aggregate_rows": len(aggregate_rows),
        "statistical_comparison_rows": len(comparison_rows),
    }
    require(
        semantic_counts == fixture["semantic_counts"],
        f"semantic counts mismatch: {semantic_counts}",
    )

    policies = tuple(config["policies"])
    seeds = tuple(int(seed) for seed in config["episode_seeds"])
    episode_groups = Counter(row["policy"] for row in episode_rows)
    require(
        episode_groups == Counter({policy: len(seeds) for policy in policies}),
        f"episode policy counts mismatch: {episode_groups}",
    )
    require(
        {int(row["episode_seed"]) for row in episode_rows} == set(seeds),
        "episode seed set mismatch",
    )
    for row in episode_rows:
        require(int(row["query_budget"]) == int(config["query_budget"]), "episode budget mismatch")
        require(int(row["unique_queries"]) == int(config["query_budget"]), "genotype query count mismatch")

    aggregate_index = {
        (row["policy"], row["metric"]): row for row in aggregate_rows
    }
    for policy, metrics in fixture["aggregate_means"].items():
        policy_rows = [row for row in episode_rows if row["policy"] == policy]
        for metric, expected in metrics.items():
            actual = statistics.fmean(float(row[metric]) for row in policy_rows)
            require_close(actual, float(expected), tolerance, f"recomputed mean {policy}/{metric}")
            require_close(
                float(aggregate_index[(policy, metric)]["mean"]),
                float(expected),
                tolerance,
                f"reported mean {policy}/{metric}",
            )

    by_policy_seed = {
        (row["policy"], int(row["episode_seed"])): row for row in episode_rows
    }
    comparison_index = {
        (row["comparison"], row["metric"]): row
        for row in comparison_rows
        if row["metric"]
    }
    for comparison, expected in fixture["paired_fidelity_comparisons"].items():
        baseline = expected["baseline"]
        differences = [
            float(by_policy_seed[("bads", seed)]["heldout_fidelity_q25"])
            - float(by_policy_seed[(baseline, seed)]["heldout_fidelity_q25"])
            for seed in seeds
        ]
        row = comparison_index[(comparison, "heldout_fidelity_q25")]
        require_close(
            statistics.fmean(differences),
            float(expected["mean_paired_difference"]),
            tolerance,
            comparison,
        )
        require_close(
            float(row["mean_paired_difference"]),
            float(expected["mean_paired_difference"]),
            tolerance,
            f"reported {comparison}",
        )
        require(int(row["bads_wins"]) == int(expected["bads_wins"]), f"wins mismatch for {comparison}")
        require(int(row["ties"]) == int(expected["ties"]), f"ties mismatch for {comparison}")
        require_close(float(row["paired_ci95_low"]), float(expected["paired_ci95_low"]), tolerance, f"low CI {comparison}")
        require_close(float(row["paired_ci95_high"]), float(expected["paired_ci95_high"]), tolerance, f"high CI {comparison}")

    require(
        gate["discovery_gate_passed"] is fixture["discovery_gate_passed"],
        "discovery gate mismatch",
    )
    for detail in gate["comparisons"]:
        fidelity_pass = (
            float(detail["fidelity_mean_difference"])
            >= float(detail["fidelity_practical_margin_required"])
            and float(detail["fidelity_ci95_low"]) > 0.0
        )
        success_pass = float(detail["success_ci95_low"]) >= float(
            detail["success_noninferiority_margin"]
        )
        require(detail["fidelity_condition_pass"] is fidelity_pass, "fidelity gate logic mismatch")
        require(detail["success_condition_pass"] is success_pass, "survival gate logic mismatch")
        require(detail["comparison_pass"] is (fidelity_pass and success_pass), "comparison gate logic mismatch")

    candidate_to_phenotype: Dict[Tuple[int, str], str] = {}
    genotypes_by_seed: Dict[int, set] = defaultdict(set)
    phenotypes_by_seed: Dict[int, List[str]] = defaultdict(list)
    for row in candidate_rows:
        seed = int(row["episode_seed"])
        cid = row["candidate_id"]
        require(cid not in genotypes_by_seed[seed], f"duplicate candidate ID for seed {seed}")
        genotypes_by_seed[seed].add(cid)
        phenotype = canonical_phenotype(row["design"])
        phenotypes_by_seed[seed].append(phenotype)
        candidate_to_phenotype[(seed, cid)] = phenotype
    duplicate_groups = 0
    duplicate_rows_beyond_first = 0
    for values in phenotypes_by_seed.values():
        counts = Counter(values)
        duplicate_groups += sum(1 for count in counts.values() if count > 1)
        duplicate_rows_beyond_first += sum(count - 1 for count in counts.values() if count > 1)
    require(duplicate_groups == fixture["phenotype_audit"]["duplicate_groups"], "phenotype duplicate-group mismatch")
    require(duplicate_rows_beyond_first == fixture["phenotype_audit"]["duplicate_rows_beyond_first"], "phenotype duplicate-row mismatch")

    query_groups: Dict[Tuple[int, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in query_rows:
        require(row["split_visible_to_policy"] == "train", "non-training query exposure")
        require(not any("heldout" in key.lower() for key in row), "held-out key in query log")
        query_groups[(int(row["episode_seed"]), row["policy"])].append(row)
    redundant_physical_queries = Counter()
    for seed in seeds:
        warmups = []
        for policy in policies:
            rows = sorted(query_groups[(seed, policy)], key=lambda row: int(row["step"]))
            require(len(rows) == int(config["query_budget"]), f"query budget mismatch for {seed}/{policy}")
            require([int(row["step"]) for row in rows] == list(range(int(config["query_budget"]))), f"query steps mismatch for {seed}/{policy}")
            ids = [row["candidate_id"] for row in rows]
            require(len(ids) == len(set(ids)), f"duplicate genotype query for {seed}/{policy}")
            phenotype_queries = [candidate_to_phenotype[(seed, cid)] for cid in ids]
            redundant_physical_queries[policy] += len(phenotype_queries) - len(set(phenotype_queries))
            warmups.append(tuple(ids[: int(config["warmup_queries"])]))
        require(len(set(warmups)) == 1, f"warm-up mismatch for seed {seed}")
    require(dict(redundant_physical_queries) == fixture["phenotype_audit"]["redundant_physical_queries_by_policy"], f"redundant physical-query mismatch: {dict(redundant_physical_queries)}")

    loss_keys = Counter()
    for row in loss_rows:
        split = row["split"]
        seed = int(row["episode_seed"])
        value = float(row["intensity_loss_rate"])
        spec = config[f"{split}_loss"]
        require(float(spec["minimum"]) <= value <= float(spec["maximum"]), "loss outside frozen bounds")
        loss_keys[(seed, split, int(row["pattern_index"]), int(row["layer_index"]), int(row["mode"]))] += 1
    require(set(loss_keys.values()) == {1}, "duplicate loss-schedule cell")
    for split in ("train", "heldout"):
        expected_count = (
            len(seeds)
            * int(config[f"{split}_loss_patterns"])
            * int(config["max_depth"])
            * int(config["modes"])
        )
        actual_count = sum(1 for row in loss_rows if row["split"] == split)
        require(actual_count == expected_count, f"loss schedule shape mismatch for {split}")

    compact_queries = read_gzip_jsonl(package_root / "evidence" / "query_log.jsonl.gz")
    compact_losses = read_gzip_csv(package_root / "evidence" / "loss_schedules.csv.gz")
    require(compact_queries == query_rows, "compressed and expanded query logs differ")
    require(compact_losses == loss_rows, "compressed and expanded loss schedules differ")

    checks = {
        "configuration": "passed",
        "semantic_counts": "passed",
        "aggregate_recomputation": "passed",
        "paired_effect_recomputation": "passed",
        "discovery_gate_logic": "passed",
        "query_fairness_and_leakage": "passed",
        "loss_schedule_shape": "passed",
        "phenotype_audit": "passed_with_4_known_duplicate_groups",
        "compressed_evidence_equivalence": "passed",
    }
    print(
        json.dumps(
            {
                "status": "v1_golden_verified",
                "fixture": str(args.fixture.resolve()),
                "archive_root": str(archive),
                "checks": checks,
                "semantic_counts": semantic_counts,
                "discovery_gate_passed": gate["discovery_gate_passed"],
                "redundant_physical_queries_by_policy": dict(redundant_physical_queries),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
