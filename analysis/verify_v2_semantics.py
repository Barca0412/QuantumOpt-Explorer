#!/usr/bin/env python3
"""Independently verify the semantic contract of a QuantumOpt-Explorer V2 run.

This is deliberately stronger than a checksum verifier.  It reconstructs the
expected experiment scale from the frozen configuration, recomputes protocol
hashes and candidate identities, and cross-checks the independently serialized
candidate, query, freeze, held-out, noise, oracle, tomography, summary, and gate
artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


PROTOCOL_CONTRACT = {
    "benchmark": "fixed-topology Perceval catalog heralded CNOT calibration",
    "candidate": "8 additive radians: 6 BS then 2 PS",
    "inputs": ["00", "01", "10", "11"],
    "primary_metric": "q25 of P(correct logical output and herald)",
    "noise": ["static BS offset", "phase error", "mode-specific LC loss"],
    "leakage_rule": "heldout evaluation unavailable before freeze",
}

PRIMARY_METRIC = "heldout_usable_success_q25"
SEARCH_POLICIES = ("random", "greedy", "bads")
ALL_POLICIES = ("catalog", *SEARCH_POLICIES)

OBSERVATION_METRICS = (
    "robust_score",
    "usable_success_q10",
    "usable_success_q25",
    "usable_success_mean",
    "conditional_truth_fidelity_q10",
    "conditional_truth_fidelity_mean",
    "herald_probability_mean",
    "false_herald_probability_mean",
    "leakage_probability_mean",
    "logical_error_probability_mean",
)

QUERY_REQUIRED_FIELDS = {
    "policy",
    "event",
    "seed",
    "split",
    "candidate_index",
    "candidate_id",
    "query_number",
    *OBSERVATION_METRICS,
    "draws",
    "candidate",
    "selection_reason",
    "budget_remaining",
    "elapsed_seconds",
    "evaluation_count",
    "stop_reason",
    "config_hash",
    "protocol_hash",
}

REQUIRED_ARTIFACTS = (
    "candidate_pool.csv",
    "comparisons.csv",
    "discovery_gate.json",
    "freeze_log.jsonl",
    "golden_summary.json",
    "heldout_results.jsonl",
    "learning_curves.csv",
    "noise_schedule.csv",
    "operational_log.jsonl",
    "postsearch_oracle.csv",
    "process_tomography.csv",
    "process_tomography.jsonl",
    "query_log.jsonl",
    "run_manifest.json",
    "statistical_comparisons.csv",
    "summary.csv",
)

CORE_HASH_ARTIFACTS = {
    "freeze_log.jsonl",
    "golden_summary.json",
    "heldout_results.jsonl",
    "query_log.jsonl",
    "run_manifest.json",
    "summary.csv",
}

ABS_TOLERANCE = 1e-12


class SemanticError(AssertionError):
    """A human-readable semantic contract violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SemanticError(message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def as_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or value is None or value == "":
        raise SemanticError(f"{label} must be a finite real number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise SemanticError(f"{label} must be a finite real number") from exc
    if not math.isfinite(result):
        raise SemanticError(f"{label} must be finite, got {value!r}")
    return result


def as_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or value is None or value == "":
        raise SemanticError(f"{label} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise SemanticError(f"{label} must be an integer") from exc
    require(str(value).strip() in {str(result), f"+{result}"}, f"{label} is not an integer: {value!r}")
    return result


def as_boolean(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise SemanticError(f"{label} must be a literal boolean, got {value!r}")


def require_close(actual: Any, expected: Any, label: str) -> None:
    left = as_number(actual, f"{label} (actual)")
    right = as_number(expected, f"{label} (expected)")
    require(
        math.isclose(left, right, rel_tol=0.0, abs_tol=ABS_TOLERANCE),
        f"{label}: {left:.17g} != {right:.17g}",
    )


def require_probability(value: Any, label: str) -> float:
    result = as_number(value, label)
    require(0.0 <= result <= 1.0, f"{label} is outside [0, 1]: {result:.17g}")
    return result


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None, f"{path.name} has no CSV header")
        return list(reader)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain one JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            require(
                isinstance(value, dict),
                f"{path.name}:{line_number} must contain a JSON object",
            )
            rows.append(value)
    return rows


def vector(values: Any, length: int, label: str) -> tuple[float, ...]:
    require(
        isinstance(values, (list, tuple)) and len(values) == length,
        f"{label} must be a length-{length} vector",
    )
    return tuple(as_number(value, f"{label}[{index}]") for index, value in enumerate(values))


def physical_candidate_key(values: Sequence[float]) -> tuple[float, ...]:
    require(len(values) == 8, "candidate vector must have length 8")
    periods = (4.0 * math.pi,) * 6 + (2.0 * math.pi,) * 2
    wrapped: list[float] = []
    for raw, period in zip(values, periods):
        value = as_number(raw, "candidate coordinate") % period
        if math.isclose(value, period, rel_tol=0.0, abs_tol=1e-12) or math.isclose(
            value, 0.0, rel_tol=0.0, abs_tol=1e-12
        ):
            value = 0.0
        wrapped.append(round(value, 12))
    return tuple(wrapped)


def candidate_digest(values: Sequence[float]) -> str:
    payload = json.dumps(list(physical_candidate_key(values)), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def unique_index(
    rows: Iterable[Mapping[str, Any]],
    fields: Sequence[str],
    label: str,
) -> dict[tuple[Any, ...], Mapping[str, Any]]:
    result: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for row_number, row in enumerate(rows, start=1):
        key = tuple(row.get(field) for field in fields)
        require(None not in key, f"{label} row {row_number} lacks key field(s) {fields}")
        require(key not in result, f"{label} contains duplicate key {key}")
        result[key] = row
    return result


def iter_hash_fields(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"config_hash", "protocol_hash"}:
                yield key, item
            yield from iter_hash_fields(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_hash_fields(item)


class Verifier:
    def __init__(self, run: Path, config_path: Path):
        self.run = run.resolve()
        self.config_path = config_path.resolve()
        self.config = read_json(self.config_path)
        self.seeds = tuple(as_integer(value, "config seed") for value in self.config["seeds"])
        self.policies = tuple(str(value) for value in self.config["policies"])
        self.pool_size = as_integer(self.config["candidate_pool_size"], "candidate_pool_size")
        self.query_budget = as_integer(self.config["query_budget"], "query_budget")
        self.warmup_queries = as_integer(self.config["warmup_queries"], "warmup_queries")
        self.train_draws = as_integer(self.config["train_draws"], "train_draws")
        self.heldout_draws = as_integer(self.config["heldout_draws"], "heldout_draws")
        self.tomography_enabled = bool(self.config.get("process_tomography", {}).get("enabled"))
        self.config_hash = sha256_json(self.config)
        self.protocol_hash = sha256_json(
            {"contract": PROTOCOL_CONTRACT, "config": self.config}
        )
        self.checks: list[dict[str, Any]] = []

        missing = [name for name in REQUIRED_ARTIFACTS if not (self.run / name).is_file()]
        require(not missing, f"run is missing required artifacts: {', '.join(missing)}")
        self.summary = read_csv(self.run / "summary.csv")
        self.candidates = read_csv(self.run / "candidate_pool.csv")
        self.queries = read_jsonl(self.run / "query_log.jsonl")
        self.freezes = read_jsonl(self.run / "freeze_log.jsonl")
        self.heldout = read_jsonl(self.run / "heldout_results.jsonl")
        self.noise = read_csv(self.run / "noise_schedule.csv")
        self.oracle = read_csv(self.run / "postsearch_oracle.csv")
        self.tomography = read_csv(self.run / "process_tomography.csv")
        self.tomography_json = read_jsonl(self.run / "process_tomography.jsonl")
        self.comparisons = read_csv(self.run / "comparisons.csv")
        self.statistical_comparisons = read_csv(
            self.run / "statistical_comparisons.csv"
        )
        self.learning = read_csv(self.run / "learning_curves.csv")
        self.operational = read_jsonl(self.run / "operational_log.jsonl")
        self.gate = read_json(self.run / "discovery_gate.json")
        self.golden = read_json(self.run / "golden_summary.json")
        self.manifest = read_json(self.run / "run_manifest.json")

    def check(self, name: str, action: Callable[[], dict[str, Any]]) -> None:
        try:
            details = action()
        except Exception as exc:  # collect independent failures into one JSON report
            self.checks.append(
                {
                    "name": name,
                    "passed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        else:
            self.checks.append({"name": name, "passed": True, "details": details})

    @property
    def expected_episode_keys(self) -> set[tuple[int, str]]:
        return {(seed, policy) for seed in self.seeds for policy in self.policies}

    def _episode_index(
        self, rows: Iterable[Mapping[str, Any]], label: str
    ) -> dict[tuple[int, str], Mapping[str, Any]]:
        result: dict[tuple[int, str], Mapping[str, Any]] = {}
        for position, row in enumerate(rows, start=1):
            key = (
                as_integer(row.get("seed"), f"{label} row {position} seed"),
                str(row.get("policy")),
            )
            require(key not in result, f"{label} contains duplicate episode {key}")
            result[key] = row
        require(
            set(result) == self.expected_episode_keys,
            f"{label} episode keys differ from the seed x policy cross-product",
        )
        return result

    def _candidate_indexes(
        self,
    ) -> tuple[
        dict[tuple[int, int], Mapping[str, Any]],
        dict[tuple[int, str], Mapping[str, Any]],
        dict[tuple[int, int], tuple[float, ...]],
    ]:
        by_index: dict[tuple[int, int], Mapping[str, Any]] = {}
        by_id: dict[tuple[int, str], Mapping[str, Any]] = {}
        vectors: dict[tuple[int, int], tuple[float, ...]] = {}
        for position, row in enumerate(self.candidates, start=1):
            seed = as_integer(row.get("seed"), f"candidate row {position} seed")
            index = as_integer(
                row.get("candidate_index"), f"candidate row {position} index"
            )
            candidate_id = str(row.get("candidate_id"))
            values = tuple(
                as_number(row.get(f"compensation_{i}"), f"candidate {seed}/{index} value {i}")
                for i in range(8)
            )
            require((seed, index) not in by_index, f"duplicate candidate index {seed}/{index}")
            require((seed, candidate_id) not in by_id, f"duplicate candidate ID {seed}/{candidate_id}")
            require(
                candidate_digest(values) == candidate_id,
                f"candidate ID does not match physical vector for {seed}/{index}",
            )
            by_index[(seed, index)] = row
            by_id[(seed, candidate_id)] = row
            vectors[(seed, index)] = values
        return by_index, by_id, vectors

    def verify_configuration(self) -> dict[str, Any]:
        require(len(self.seeds) == len(set(self.seeds)), "configuration has duplicate seeds")
        require(self.policies == ALL_POLICIES, f"policy order must be {ALL_POLICIES}")
        require(self.pool_size >= self.query_budget > 0, "invalid pool/query scale")
        require(0 < self.warmup_queries <= self.query_budget, "invalid warm-up scale")
        require(self.train_draws > 0 and self.heldout_draws > 0, "noise draws must be positive")

        # The release protocol has an exact preregistered scale.  The smoke
        # profile remains valid for development and is checked at its own scale.
        if str(self.config.get("protocol_version")) == "2.0":
            observed = (
                len(self.seeds),
                self.pool_size,
                self.query_budget,
                self.warmup_queries,
                self.train_draws,
                self.heldout_draws,
                self.tomography_enabled,
            )
            expected = (8, 128, 32, 4, 8, 16, True)
            require(observed == expected, f"V2 pilot scale changed: {observed} != {expected}")
        return {
            "protocol_version": self.config.get("protocol_version"),
            "seeds": len(self.seeds),
            "policies": list(self.policies),
            "candidate_pool_size_per_seed": self.pool_size,
            "query_budget_per_search_policy": self.query_budget,
            "shared_warmup_queries": self.warmup_queries,
            "noise_draws_per_seed": {"train": self.train_draws, "heldout": self.heldout_draws},
            "tomography_enabled": self.tomography_enabled,
        }

    def verify_summary(self) -> dict[str, Any]:
        summary = self._episode_index(self.summary, "summary")
        candidate_by_index, candidate_by_id, _ = self._candidate_indexes()
        require(
            len(self.summary) == len(self.seeds) * len(self.policies),
            "summary row count mismatch",
        )
        for (seed, policy), row in summary.items():
            expected_queries = 1 if policy == "catalog" else self.query_budget
            require(
                as_integer(row.get("queries_used"), f"summary {seed}/{policy} queries")
                == expected_queries,
                f"summary query count mismatch for {seed}/{policy}",
            )
            index = as_integer(
                row.get("selected_candidate_index"), f"summary {seed}/{policy} index"
            )
            candidate_id = str(row.get("selected_candidate_id"))
            require((seed, index) in candidate_by_index, f"summary references unknown index {seed}/{index}")
            require((seed, candidate_id) in candidate_by_id, f"summary references unknown ID {seed}/{candidate_id}")
            require(
                candidate_by_index[(seed, index)]["candidate_id"] == candidate_id,
                f"summary candidate index/ID disagree for {seed}/{policy}",
            )
            for coordinate in range(8):
                require_close(
                    row.get(f"compensation_{coordinate}"),
                    candidate_by_index[(seed, index)][f"compensation_{coordinate}"],
                    f"summary candidate coordinate {seed}/{policy}/{coordinate}",
                )
            for split in ("train", "heldout"):
                for metric in OBSERVATION_METRICS:
                    require_probability(
                        row.get(f"{split}_{metric}"),
                        f"summary {seed}/{policy} {split}_{metric}",
                    )
                require_close(
                    row.get(f"{split}_robust_score"),
                    row.get(f"{split}_usable_success_q25"),
                    f"summary robust/q25 {seed}/{policy}/{split}",
                )
            require_probability(
                row.get("heldout_oracle_usable_success_q25"),
                f"summary {seed}/{policy} oracle metric",
            )
            require_probability(
                row.get("heldout_regret_q25"), f"summary {seed}/{policy} regret"
            )
        return {
            "rows": len(self.summary),
            "expected": len(self.seeds) * len(self.policies),
            "episodes": len(summary),
        }

    def verify_candidate_pool(self) -> dict[str, Any]:
        by_index, _, vectors = self._candidate_indexes()
        for seed in self.seeds:
            indexes = {index for candidate_seed, index in by_index if candidate_seed == seed}
            require(
                indexes == set(range(self.pool_size)),
                f"candidate indexes for seed {seed} are not 0..{self.pool_size - 1}",
            )
            physical = [
                physical_candidate_key(vectors[(seed, index)]) for index in range(self.pool_size)
            ]
            require(
                len(physical) == len(set(physical)),
                f"candidate pool has a physical duplicate for seed {seed}",
            )
        return {
            "rows": len(self.candidates),
            "per_seed": self.pool_size,
            "candidate_ids_recomputed": len(self.candidates),
            "physical_duplicates": 0,
        }

    def verify_queries(self) -> dict[str, Any]:
        candidate_by_index, _, candidate_vectors = self._candidate_indexes()
        summary = self._episode_index(self.summary, "summary")
        grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
        for position, row in enumerate(self.queries, start=1):
            missing = QUERY_REQUIRED_FIELDS - set(row)
            require(not missing, f"query row {position} lacks fields: {sorted(missing)}")
            serialized = canonical_json(row).lower()
            require("heldout" not in serialized, f"query row {position} contains heldout text")
            require(row["event"] == "query", f"query row {position} has wrong event")
            require(row["split"] == "train", f"query row {position} is not train-only")
            elapsed = as_number(row["elapsed_seconds"], f"query row {position} elapsed_seconds")
            require(elapsed >= 0.0, f"query row {position} elapsed_seconds is negative")
            seed = as_integer(row["seed"], f"query row {position} seed")
            policy = str(row["policy"])
            require((seed, policy) in self.expected_episode_keys, f"unknown query episode {seed}/{policy}")
            query_number = as_integer(row["query_number"], f"query row {position} number")
            index = as_integer(row["candidate_index"], f"query row {position} candidate index")
            require((seed, index) in candidate_by_index, f"query row {position} has unknown candidate")
            candidate_id = str(row["candidate_id"])
            require(
                candidate_by_index[(seed, index)]["candidate_id"] == candidate_id,
                f"query row {position} candidate ID/index mismatch",
            )
            values = vector(row["candidate"], 8, f"query row {position} candidate")
            require(
                all(
                    math.isclose(left, right, rel_tol=0.0, abs_tol=ABS_TOLERANCE)
                    for left, right in zip(values, candidate_vectors[(seed, index)])
                ),
                f"query row {position} candidate vector differs from pool",
            )
            require(candidate_digest(values) == candidate_id, f"query row {position} physical ID mismatch")
            require(
                as_integer(row["draws"], f"query row {position} draws") == self.train_draws,
                f"query row {position} train draw count mismatch",
            )
            require(
                as_integer(row["evaluation_count"], f"query row {position} evaluations")
                == self.train_draws * 4,
                f"query row {position} evaluation count mismatch",
            )
            require(
                as_integer(row["budget_remaining"], f"query row {position} budget")
                == self.query_budget - query_number,
                f"query row {position} remaining budget mismatch",
            )
            for metric in OBSERVATION_METRICS:
                require_probability(row[metric], f"query row {position} {metric}")
            require_close(
                row["robust_score"], row["usable_success_q25"], f"query row {position} robust/q25"
            )
            grouped[(seed, policy)].append(row)

        require(set(grouped) == self.expected_episode_keys, "query episodes are incomplete")
        for key, rows in grouped.items():
            seed, policy = key
            ordered = sorted(rows, key=lambda row: as_integer(row["query_number"], "query number"))
            expected_count = 1 if policy == "catalog" else self.query_budget
            require(len(ordered) == expected_count, f"query count mismatch for {seed}/{policy}")
            require(
                [as_integer(row["query_number"], "query number") for row in ordered]
                == list(range(1, expected_count + 1)),
                f"query numbers are not sequential for {seed}/{policy}",
            )
            physical = [physical_candidate_key(vector(row["candidate"], 8, "query candidate")) for row in ordered]
            require(len(physical) == len(set(physical)), f"physical query duplicate for {seed}/{policy}")
            selected_id = str(summary[key]["selected_candidate_id"])
            require(
                selected_id in {str(row["candidate_id"]) for row in ordered},
                f"selected candidate was never queried for {seed}/{policy}",
            )
            selected_query = next(
                row for row in ordered if str(row["candidate_id"]) == selected_id
            )
            for metric in OBSERVATION_METRICS:
                require_close(
                    selected_query[metric],
                    summary[key][f"train_{metric}"],
                    f"selected query/summary train metric {seed}/{policy}/{metric}",
                )
            if policy == "catalog":
                require(
                    as_integer(ordered[0]["candidate_index"], "catalog candidate") == 0,
                    f"catalog does not query candidate 0 for seed {seed}",
                )

        for seed in self.seeds:
            warmups = [
                tuple(
                    str(row["candidate_id"])
                    for row in sorted(
                        grouped[(seed, policy)],
                        key=lambda row: as_integer(row["query_number"], "query number"),
                    )[: self.warmup_queries]
                )
                for policy in SEARCH_POLICIES
            ]
            require(len(set(warmups)) == 1, f"shared warm-up candidates differ for seed {seed}")
        expected_rows = len(self.seeds) * (1 + len(SEARCH_POLICIES) * self.query_budget)
        require(len(self.queries) == expected_rows, "total query count mismatch")
        return {
            "rows": len(self.queries),
            "catalog_queries_per_seed": 1,
            "search_queries_per_seed_policy": self.query_budget,
            "shared_candidate_ids_per_search_policy": self.warmup_queries,
            "physical_duplicates_within_episode": 0,
            "heldout_text_occurrences": 0,
        }

    def verify_freeze_heldout_boundary(self) -> dict[str, Any]:
        summary = self._episode_index(self.summary, "summary")
        freezes = self._episode_index(self.freezes, "freeze log")
        heldout = self._episode_index(self.heldout, "heldout results")
        query_groups = Counter(
            (as_integer(row["seed"], "query seed"), str(row["policy"]))
            for row in self.queries
        )
        candidate_by_index, _, candidate_vectors = self._candidate_indexes()
        for key in sorted(self.expected_episode_keys):
            seed, policy = key
            freeze = freezes[key]
            result = heldout[key]
            final = summary[key]
            require(freeze.get("event") == "freeze", f"wrong freeze event for {seed}/{policy}")
            require(
                result.get("event") == "heldout_evaluation",
                f"wrong heldout event for {seed}/{policy}",
            )
            expected_queries = 1 if policy == "catalog" else self.query_budget
            require(query_groups[key] == expected_queries, f"query/freeze count mismatch for {seed}/{policy}")
            require(
                as_integer(freeze.get("queries_used"), f"freeze {seed}/{policy} queries")
                == expected_queries,
                f"freeze query count mismatch for {seed}/{policy}",
            )
            freeze_index = as_integer(
                freeze.get("selected_candidate_index"), f"freeze {seed}/{policy} index"
            )
            heldout_index = as_integer(
                result.get("candidate_index"), f"heldout {seed}/{policy} index"
            )
            summary_index = as_integer(
                final.get("selected_candidate_index"), f"summary {seed}/{policy} index"
            )
            require(
                freeze_index == heldout_index == summary_index,
                f"freeze/heldout/summary candidate index mismatch for {seed}/{policy}",
            )
            freeze_id = str(freeze.get("selected_candidate_id"))
            heldout_id = str(result.get("candidate_id"))
            summary_id = str(final.get("selected_candidate_id"))
            require(
                freeze_id == heldout_id == summary_id,
                f"freeze/heldout/summary candidate ID mismatch for {seed}/{policy}",
            )
            require((seed, freeze_index) in candidate_by_index, f"unknown frozen candidate {seed}/{policy}")
            values = vector(result.get("candidate"), 8, f"heldout {seed}/{policy} candidate")
            require(
                all(
                    math.isclose(left, right, rel_tol=0.0, abs_tol=ABS_TOLERANCE)
                    for left, right in zip(values, candidate_vectors[(seed, freeze_index)])
                ),
                f"heldout candidate vector mismatch for {seed}/{policy}",
            )
            require(result.get("split") == "heldout", f"wrong heldout split for {seed}/{policy}")
            require(result.get("query_number") is None, f"heldout query_number must be null for {seed}/{policy}")
            require(
                as_integer(result.get("draws"), f"heldout {seed}/{policy} draws")
                == self.heldout_draws,
                f"heldout draw count mismatch for {seed}/{policy}",
            )
            for metric in OBSERVATION_METRICS:
                require_probability(result.get(metric), f"heldout {seed}/{policy} {metric}")
                require_close(
                    result.get(metric),
                    final.get(f"heldout_{metric}"),
                    f"heldout/summary metric {seed}/{policy}/{metric}",
                )
        return {
            "freeze_rows": len(self.freezes),
            "heldout_rows": len(self.heldout),
            "matched_freeze_then_heldout_pairs": len(self.expected_episode_keys),
            "boundary_evidence": "one freeze record maps 1:1 to each separately recorded heldout evaluation; query log is train-only",
        }

    def verify_noise_schedule(self) -> dict[str, Any]:
        observed: set[tuple[int, str, int]] = set()
        counts: Counter[tuple[int, str]] = Counter()
        static_bs: dict[int, tuple[float, ...]] = {}
        for position, row in enumerate(self.noise, start=1):
            seed = as_integer(row.get("seed"), f"noise row {position} seed")
            split = str(row.get("split"))
            require(seed in self.seeds, f"noise row {position} has undeclared seed")
            require(split in {"train", "heldout"}, f"noise row {position} has invalid split")
            index = as_integer(row.get("draw_index"), f"noise row {position} draw index")
            key = (seed, split, index)
            require(key not in observed, f"duplicate noise draw {key}")
            observed.add(key)
            counts[(seed, split)] += 1
            bs = tuple(as_number(row.get(f"bs_offset_{i}"), f"noise {key} bs {i}") for i in range(6))
            phase = tuple(as_number(row.get(f"phase_error_{i}"), f"noise {key} phase {i}") for i in range(2))
            losses = tuple(require_probability(row.get(f"mode_loss_{i}"), f"noise {key} loss {i}") for i in range(6))
            del phase
            if seed in static_bs:
                require(bs == static_bs[seed], f"static BS offset changes within seed {seed}")
            else:
                static_bs[seed] = bs
            require_close(
                row.get("mean_mode_loss"),
                sum(losses) / len(losses),
                f"noise {key} mean mode loss",
            )
            lower, upper = (
                as_number(value, f"config {split} loss clip")
                for value in self.config["noise"][split]["loss_clip"]
            )
            require(
                all(lower <= value <= upper for value in losses),
                f"noise loss is outside configured clip for {key}",
            )
        for seed in self.seeds:
            require(counts[(seed, "train")] == self.train_draws, f"train noise count mismatch for seed {seed}")
            require(counts[(seed, "heldout")] == self.heldout_draws, f"heldout noise count mismatch for seed {seed}")
            require(
                {index for s, split, index in observed if s == seed and split == "train"}
                == set(range(self.train_draws)),
                f"train noise draw indexes mismatch for seed {seed}",
            )
            require(
                {index for s, split, index in observed if s == seed and split == "heldout"}
                == set(range(self.heldout_draws)),
                f"heldout noise draw indexes mismatch for seed {seed}",
            )
        return {
            "rows": len(self.noise),
            "per_seed": {"train": self.train_draws, "heldout": self.heldout_draws},
            "unique_draw_keys": len(observed),
        }

    def verify_postsearch_oracle(self) -> dict[str, Any]:
        candidate_by_index, _, _ = self._candidate_indexes()
        summary = self._episode_index(self.summary, "summary")
        oracle: dict[tuple[int, int], Mapping[str, Any]] = {}
        for position, row in enumerate(self.oracle, start=1):
            seed = as_integer(row.get("seed"), f"oracle row {position} seed")
            index = as_integer(row.get("candidate_index"), f"oracle row {position} index")
            key = (seed, index)
            require(key not in oracle, f"duplicate oracle candidate {key}")
            require(key in candidate_by_index, f"oracle references unknown candidate {key}")
            require(
                str(row.get("candidate_id")) == candidate_by_index[key]["candidate_id"],
                f"oracle candidate ID mismatch for {key}",
            )
            require(as_boolean(row.get("context_only"), f"oracle {key} context_only"), f"oracle {key} is not context-only")
            require(
                not as_boolean(row.get("available_to_policy"), f"oracle {key} available_to_policy"),
                f"oracle {key} was available to a policy",
            )
            require(row.get("split") == "heldout", f"oracle {key} is not heldout")
            require(row.get("query_number") in {"", None}, f"oracle {key} has a query number")
            require(
                as_integer(row.get("draws"), f"oracle {key} draws") == self.heldout_draws,
                f"oracle draw count mismatch for {key}",
            )
            for metric in OBSERVATION_METRICS:
                require_probability(row.get(metric), f"oracle {key} {metric}")
            oracle[key] = row
        for seed in self.seeds:
            indexes = {index for candidate_seed, index in oracle if candidate_seed == seed}
            require(indexes == set(range(self.pool_size)), f"oracle coverage mismatch for seed {seed}")
            best_index = max(
                indexes,
                key=lambda index: (
                    as_number(oracle[(seed, index)]["usable_success_q25"], "oracle q25"),
                    -index,
                ),
            )
            best = oracle[(seed, best_index)]
            for policy in self.policies:
                row = summary[(seed, policy)]
                require(
                    as_integer(row.get("heldout_oracle_candidate_index"), "summary oracle index")
                    == best_index,
                    f"summary oracle index mismatch for {seed}/{policy}",
                )
                require(
                    str(row.get("heldout_oracle_candidate_id")) == str(best["candidate_id"]),
                    f"summary oracle ID mismatch for {seed}/{policy}",
                )
                require_close(
                    row.get("heldout_oracle_usable_success_q25"),
                    best["usable_success_q25"],
                    f"summary oracle value {seed}/{policy}",
                )
                expected_regret = max(
                    0.0,
                    as_number(best["usable_success_q25"], "oracle best")
                    - as_number(row["heldout_usable_success_q25"], "summary heldout"),
                )
                require_close(row.get("heldout_regret_q25"), expected_regret, f"summary regret {seed}/{policy}")
        return {
            "rows": len(self.oracle),
            "per_seed": self.pool_size,
            "available_to_policy_true": 0,
            "summary_oracle_links_verified": len(self.summary),
        }

    def verify_tomography(self) -> dict[str, Any]:
        summary = self._episode_index(self.summary, "summary")
        scalar = self._episode_index(self.tomography, "tomography CSV")
        detailed = self._episode_index(self.tomography_json, "tomography JSONL")
        draw_index = as_integer(
            self.config.get("process_tomography", {}).get("heldout_draw_index", 0),
            "tomography heldout_draw_index",
        )
        require(0 <= draw_index < self.heldout_draws, "tomography draw index is out of range")
        completed = 0
        scalar_metrics = (
            "average_gate_fidelity",
            "gate_efficiency",
            "chi_trace_real",
            "chi_trace_imag",
            "chi_hermiticity_residual",
        )
        for key in sorted(self.expected_episode_keys):
            row = scalar[key]
            detail = detailed[key]
            status = str(row.get("tomography_status"))
            expected_status = "completed" if self.tomography_enabled else "disabled_by_config"
            require(status == expected_status, f"tomography status mismatch for {key}")
            require(detail.get("tomography_status") == status, f"tomography CSV/JSON status mismatch for {key}")
            require(
                str(row.get("selected_candidate_id")) == str(summary[key]["selected_candidate_id"]),
                f"tomography/summary finalist mismatch for {key}",
            )
            require(
                as_integer(row.get("selected_candidate_index"), f"tomography {key} index")
                == as_integer(summary[key]["selected_candidate_index"], f"summary {key} index"),
                f"tomography/summary finalist index mismatch for {key}",
            )
            require(
                as_integer(row.get("heldout_draw_index"), f"tomography {key} draw") == draw_index,
                f"tomography draw mismatch for {key}",
            )
            if not self.tomography_enabled:
                continue
            completed += 1
            for metric in scalar_metrics:
                value = as_number(row.get(metric), f"tomography {key} {metric}")
                require_close(value, detail.get(metric), f"tomography CSV/JSON {key}/{metric}")
            require_probability(row["average_gate_fidelity"], f"tomography {key} average fidelity")
            require_probability(row["gate_efficiency"], f"tomography {key} gate efficiency")
            require(
                as_number(row["chi_hermiticity_residual"], f"tomography {key} residual") >= 0.0,
                f"tomography residual is negative for {key}",
            )
            real = detail.get("chi_real")
            imag = detail.get("chi_imag")
            require(isinstance(real, list) and isinstance(imag, list), f"tomography matrices missing for {key}")
            require(len(real) == len(imag) > 0, f"tomography matrix shape mismatch for {key}")
            for matrix_name, matrix in (("chi_real", real), ("chi_imag", imag)):
                width: int | None = None
                for row_number, matrix_row in enumerate(matrix):
                    require(isinstance(matrix_row, list) and matrix_row, f"{matrix_name} row invalid for {key}")
                    width = len(matrix_row) if width is None else width
                    require(len(matrix_row) == width, f"{matrix_name} is ragged for {key}")
                    for column, value in enumerate(matrix_row):
                        as_number(value, f"tomography {key} {matrix_name}[{row_number}][{column}]")
        expected_completed = len(self.seeds) * len(self.policies) if self.tomography_enabled else 0
        require(completed == expected_completed, "completed tomography count mismatch")
        return {
            "rows": len(self.tomography),
            "completed": completed,
            "expected_completed": expected_completed,
            "scalar_metrics_finite": completed * len(scalar_metrics),
        }

    def verify_hash_consistency(self) -> dict[str, Any]:
        occurrences: Counter[str] = Counter()
        files_with_hashes: set[str] = set()
        for path in sorted(self.run.iterdir()):
            if not path.is_file() or path.suffix not in {".csv", ".json", ".jsonl"}:
                continue
            values: list[Any]
            if path.suffix == ".csv":
                values = read_csv(path)
            elif path.suffix == ".jsonl":
                values = read_jsonl(path)
            else:
                values = [read_json(path)]
            for record_number, value in enumerate(values, start=1):
                if path.name in CORE_HASH_ARTIFACTS:
                    require(
                        isinstance(value, dict)
                        and "config_hash" in value
                        and "protocol_hash" in value,
                        f"{path.name} record {record_number} lacks a config/protocol hash pair",
                    )
                fields = list(iter_hash_fields(value))
                if fields:
                    files_with_hashes.add(path.name)
                for key, actual in fields:
                    expected = self.config_hash if key == "config_hash" else self.protocol_hash
                    require(actual == expected, f"{path.name} has inconsistent {key}")
                    occurrences[key] += 1
        require(
            CORE_HASH_ARTIFACTS <= files_with_hashes,
            f"core artifacts missing hash fields: {sorted(CORE_HASH_ARTIFACTS - files_with_hashes)}",
        )
        require(occurrences["config_hash"] > 0 and occurrences["protocol_hash"] > 0, "hash fields absent")
        require(self.manifest.get("primary_metric") == PRIMARY_METRIC, "manifest primary metric mismatch")
        require(self.golden.get("primary_metric") == PRIMARY_METRIC, "golden primary metric mismatch")
        require(
            tuple(as_integer(value, "manifest seed") for value in self.manifest.get("seeds", []))
            == self.seeds,
            "manifest seed list differs from configuration",
        )
        require(
            tuple(str(value) for value in self.manifest.get("policies", [])) == self.policies,
            "manifest policy list differs from configuration",
        )
        require(
            as_integer(self.golden.get("summary_rows"), "golden summary_rows")
            == len(self.summary),
            "golden summary row count differs from artifact",
        )
        require(
            as_integer(self.golden.get("query_rows"), "golden query_rows")
            == len(self.queries),
            "golden query row count differs from artifact",
        )
        return {
            "recomputed_config_hash": self.config_hash,
            "recomputed_protocol_hash": self.protocol_hash,
            "files_with_hashes": sorted(files_with_hashes),
            "occurrences": dict(occurrences),
        }

    def verify_auxiliary_metrics(self) -> dict[str, Any]:
        summary = self._episode_index(self.summary, "summary")
        for position, row in enumerate(self.learning, start=1):
            require_probability(
                row.get("observed_usable_success_q25"), f"learning row {position} observed"
            )
            require_probability(
                row.get("best_so_far_usable_success_q25"), f"learning row {position} best"
            )
        require(
            self.comparisons == self.statistical_comparisons,
            "comparisons.csv and statistical_comparisons.csv differ",
        )
        expected_pair_keys = {
            ("random", "catalog"),
            ("greedy", "catalog"),
            ("bads", "catalog"),
            ("greedy", "random"),
            ("bads", "random"),
            ("bads", "greedy"),
        }
        observed_pair_keys: set[tuple[str, str]] = set()
        for position, row in enumerate(self.comparisons, start=1):
            pair = (str(row.get("policy")), str(row.get("reference")))
            require(pair not in observed_pair_keys, f"duplicate comparison pair {pair}")
            require(pair in expected_pair_keys, f"unexpected comparison pair {pair}")
            observed_pair_keys.add(pair)
            n = as_integer(row.get("n_paired_seeds"), f"comparison row {position} n")
            wins = as_integer(row.get("wins"), f"comparison row {position} wins")
            ties = as_integer(row.get("ties"), f"comparison row {position} ties")
            require(n == len(self.seeds), f"comparison row {position} seed count mismatch")
            require(0 <= wins <= n and 0 <= ties <= n, f"comparison row {position} count out of range")
            for field in (
                "mean_difference_heldout_usable_success_q25",
                "sd_paired_difference",
                "normal_approx_ci95_low",
                "normal_approx_ci95_high",
                "mean_relative_improvement",
                "mean_difference_conditional_truth_fidelity",
            ):
                as_number(row.get(field), f"comparison row {position} {field}")
            policy, reference = pair
            primary = [
                as_number(summary[(seed, policy)][PRIMARY_METRIC], "comparison policy primary")
                - as_number(summary[(seed, reference)][PRIMARY_METRIC], "comparison reference primary")
                for seed in self.seeds
            ]
            reference_values = [
                as_number(summary[(seed, reference)][PRIMARY_METRIC], "comparison reference primary")
                for seed in self.seeds
            ]
            fidelity = [
                as_number(
                    summary[(seed, policy)]["heldout_conditional_truth_fidelity_mean"],
                    "comparison policy fidelity",
                )
                - as_number(
                    summary[(seed, reference)]["heldout_conditional_truth_fidelity_mean"],
                    "comparison reference fidelity",
                )
                for seed in self.seeds
            ]
            mean_difference = sum(primary) / n
            sample_sd = math.sqrt(
                sum((value - mean_difference) ** 2 for value in primary) / (n - 1)
            ) if n > 1 else 0.0
            half_width = 1.96 * sample_sd / math.sqrt(n)
            require(as_integer(row["wins"], "reported wins") == sum(value > 0 for value in primary), f"wins mismatch for {pair}")
            require(
                as_integer(row["ties"], "reported ties")
                == sum(math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1e-15) for value in primary),
                f"ties mismatch for {pair}",
            )
            require_close(row["mean_difference_heldout_usable_success_q25"], mean_difference, f"mean difference {pair}")
            require_close(row["sd_paired_difference"], sample_sd, f"paired SD {pair}")
            require_close(row["normal_approx_ci95_low"], mean_difference - half_width, f"CI low {pair}")
            require_close(row["normal_approx_ci95_high"], mean_difference + half_width, f"CI high {pair}")
            require_close(
                row["mean_relative_improvement"],
                sum(
                    difference / max(abs(reference_value), 1e-15)
                    for difference, reference_value in zip(primary, reference_values)
                )
                / n,
                f"mean relative difference {pair}",
            )
            require_close(
                row["mean_difference_conditional_truth_fidelity"],
                sum(fidelity) / n,
                f"mean fidelity difference {pair}",
            )
        require(observed_pair_keys == expected_pair_keys, "comparison pair set mismatch")
        for position, row in enumerate(self.operational, start=1):
            require(row.get("event") == "query_timing", f"operational row {position} event mismatch")
            elapsed = as_number(row.get("elapsed_seconds"), f"operational row {position} elapsed")
            require(elapsed >= 0.0, f"operational row {position} elapsed is negative")
        require(len(self.operational) == len(self.queries), "operational/query row count mismatch")
        return {
            "primary_metric": PRIMARY_METRIC,
            "learning_rows_checked": len(self.learning),
            "comparison_rows_checked": len(self.comparisons),
            "operational_rows_checked": len(self.operational),
        }

    def verify_gate(self) -> dict[str, Any]:
        summary = self._episode_index(self.summary, "summary")
        spec = self.config["gate"]
        target = str(spec["policy"])
        references = ("catalog", "random")
        min_wins = as_integer(spec["min_wins"], "gate min_wins")
        min_relative = as_number(spec["min_relative_improvement"], "gate min relative")
        fidelity_margin = as_number(
            spec["max_conditional_fidelity_decline"], "gate fidelity margin"
        )
        quantitative_checks: list[bool] = []
        reversal = False
        gate_details: dict[str, Any] = {}
        reversal_required = as_integer(
            spec["stable_reversal_min_seeds"], "gate reversal minimum"
        )
        for reference in references:
            primary_differences: list[float] = []
            fidelity_differences: list[float] = []
            relative_differences: list[float] = []
            positive_to_negative = 0
            negative_to_positive = 0
            for seed in self.seeds:
                target_row = summary[(seed, target)]
                reference_row = summary[(seed, reference)]
                target_heldout = as_number(target_row[PRIMARY_METRIC], "target heldout primary")
                reference_heldout = as_number(reference_row[PRIMARY_METRIC], "reference heldout primary")
                difference = target_heldout - reference_heldout
                primary_differences.append(difference)
                relative_differences.append(difference / max(abs(reference_heldout), 1e-15))
                fidelity_differences.append(
                    as_number(
                        target_row["heldout_conditional_truth_fidelity_mean"],
                        "target heldout fidelity",
                    )
                    - as_number(
                        reference_row["heldout_conditional_truth_fidelity_mean"],
                        "reference heldout fidelity",
                    )
                )
                train_difference = as_number(
                    target_row["train_usable_success_q25"], "target train primary"
                ) - as_number(reference_row["train_usable_success_q25"], "reference train primary")
                positive_to_negative += int(train_difference > 0 and difference < 0)
                negative_to_positive += int(train_difference < 0 and difference > 0)
            wins = sum(value > 0 for value in primary_differences)
            mean_relative = sum(relative_differences) / len(relative_differences)
            mean_fidelity = sum(fidelity_differences) / len(fidelity_differences)
            reference_pass = (
                wins >= min_wins
                and mean_relative >= min_relative
                and mean_fidelity >= -fidelity_margin
            )
            quantitative_checks.append(reference_pass)
            stable_reference = max(positive_to_negative, negative_to_positive) >= reversal_required
            reversal = reversal or stable_reference
            gate_details[reference] = {
                "wins": wins,
                "mean_relative_improvement": mean_relative,
                "mean_conditional_fidelity_difference": mean_fidelity,
                "quantitative_pass": reference_pass,
                "train_positive_heldout_negative": positive_to_negative,
                "train_negative_heldout_positive": negative_to_positive,
                "stable_reversal": stable_reference,
            }
        quantitative = bool(quantitative_checks) and all(quantitative_checks)
        expected_outcome = "A" if quantitative else "B" if reversal else "C"
        actual_outcome = self.gate.get("outcome_class")
        require(actual_outcome in {"A", "B", "C"}, f"invalid gate outcome {actual_outcome!r}")
        require(actual_outcome == expected_outcome, f"gate outcome {actual_outcome} != recomputed {expected_outcome}")
        require(
            self.gate.get("quantitative_signal_pass") is quantitative,
            "gate quantitative_signal_pass mismatch",
        )
        require(
            self.gate.get("predeclared_A_gate_pass") is quantitative,
            "gate predeclared_A_gate_pass mismatch",
        )
        require(
            self.gate.get("stable_train_heldout_ranking_reversal") is reversal,
            "gate stable reversal mismatch",
        )
        require(self.gate.get("primary_metric") == PRIMARY_METRIC, "gate primary metric mismatch")
        require(self.gate.get("target_policy") == target, "gate target policy mismatch")
        require(self.gate.get("discovery_claim_pass") is False, "discovery claim must remain false")
        definitions = self.gate.get("outcome_definition")
        require(isinstance(definitions, dict) and set(definitions) == {"A", "B", "C"}, "gate lacks A/B/C definitions")
        return {
            "reported_outcome": actual_outcome,
            "recomputed_outcome": expected_outcome,
            "quantitative_signal_pass": quantitative,
            "stable_ranking_reversal": reversal,
            "reference_checks": gate_details,
        }

    def run_checks(self) -> dict[str, Any]:
        for name, action in (
            ("configuration_and_scale", self.verify_configuration),
            ("summary_seed_policy_cross_product", self.verify_summary),
            ("candidate_pool_identity_and_physical_uniqueness", self.verify_candidate_pool),
            ("query_budget_warmup_schema_and_no_leakage", self.verify_queries),
            ("freeze_then_heldout_cross_file_boundary", self.verify_freeze_heldout_boundary),
            ("noise_schedule_shape", self.verify_noise_schedule),
            ("postsearch_oracle_is_context_only", self.verify_postsearch_oracle),
            ("process_tomography_completion_and_finiteness", self.verify_tomography),
            ("recomputed_config_and_protocol_hash_consistency", self.verify_hash_consistency),
            ("primary_and_auxiliary_metric_domains", self.verify_auxiliary_metrics),
            ("gate_outcome_recomputation", self.verify_gate),
        ):
            self.check(name, action)
        failures = [check for check in self.checks if not check["passed"]]
        return {
            "schema_version": 1,
            "verifier": "QuantumOpt-Explorer V2 semantic verifier",
            "status": "passed" if not failures else "failed",
            "run": str(self.run),
            "config": str(self.config_path),
            "checks_passed": len(self.checks) - len(failures),
            "checks_total": len(self.checks),
            "errors": [check["error"] for check in failures],
            "checks": self.checks,
        }


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=repository / "runs" / "v2")
    parser.add_argument("--config", type=Path, default=repository / "configs" / "v2_pilot.json")
    return parser.parse_args()


def failure_report(run: Path, config: Path, exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "verifier": "QuantumOpt-Explorer V2 semantic verifier",
        "status": "failed",
        "run": str(run.resolve()),
        "config": str(config.resolve()),
        "checks_passed": 0,
        "checks_total": 0,
        "errors": [f"{type(exc).__name__}: {exc}"],
        "checks": [],
    }


def main() -> int:
    args = parse_args()
    try:
        report = Verifier(args.run, args.config).run_checks()
    except Exception as exc:
        report = failure_report(args.run, args.config, exc)
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
