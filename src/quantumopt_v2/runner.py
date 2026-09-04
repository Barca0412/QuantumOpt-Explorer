"""Experiment orchestration, deterministic artifacts, and verification."""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import perceval as pcvl

from .circuit import process_tomography
from .environment import CalibrationEnvironment, Observation, candidate_id, validate_config
from .policies import PolicyResult, run_policy
from .protocol import canonical_json, config_hash, protocol_hash


ARTIFACT_NAMES = (
    "candidate_pool.csv",
    "comparisons.csv",
    "discovery_gate.json",
    "freeze_log.jsonl",
    "golden_summary.json",
    "heldout_results.jsonl",
    "heldout_tradeoff.png",
    "learning_curves.csv",
    "learning_curves.png",
    "noise_schedule.csv",
    "operational_log.jsonl",
    "postsearch_oracle.csv",
    "process_tomography.csv",
    "process_tomography.jsonl",
    "query_log.jsonl",
    "statistical_comparisons.csv",
    "summary.csv",
)


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    validate_config(config)
    return config


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_text(path: Path, text: str) -> None:
    _atomic_write(path, text.encode("utf-8"))


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    lines = [canonical_json(row) for row in rows]
    _write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    _write_text(path, buffer.getvalue())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _semantic_query_hash(path: Path) -> str:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    for row in rows:
        row["elapsed_seconds"] = None
    payload = "\n".join(canonical_json(row) for row in rows)
    if rows:
        payload += "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prefix(prefix: str, observation: Observation) -> dict[str, Any]:
    excluded = {"split", "candidate_index", "candidate_id", "query_number", "draws"}
    return {
        f"{prefix}_{key}": value
        for key, value in observation.to_dict().items()
        if key not in excluded
    }


def _summary_row(seed: int, result: PolicyResult, env: CalibrationEnvironment) -> dict[str, Any]:
    selected = env.candidate(result.selected_candidate_index)
    return {
        "seed": seed,
        "policy": result.policy,
        "queries_used": result.queries_used,
        "selected_candidate_index": result.selected_candidate_index,
        "selected_candidate_id": result.selected_train_observation.candidate_id,
        **{f"compensation_{index}": float(value) for index, value in enumerate(selected)},
        **_prefix("train", result.selected_train_observation),
        **_prefix("heldout", result.heldout_observation),
        "config_hash": env.config_hash,
        "protocol_hash": env.protocol_hash,
    }


def _comparison_rows(summary_rows: list[dict[str, Any]], policies: list[str]) -> list[dict[str, Any]]:
    by_policy = {
        policy: {int(row["seed"]): row for row in summary_rows if row["policy"] == policy}
        for policy in policies
    }
    pairs: list[tuple[str, str]] = []
    if "catalog" in policies:
        pairs.extend((policy, "catalog") for policy in policies if policy != "catalog")
    if "random" in policies:
        pairs.extend(
            (policy, "random")
            for policy in policies
            if policy not in {"catalog", "random"}
        )
    if "bads" in policies and "greedy" in policies:
        pairs.append(("bads", "greedy"))
    rows: list[dict[str, Any]] = []
    for policy, reference in pairs:
        common = sorted(set(by_policy[policy]) & set(by_policy[reference]))
        primary = np.asarray(
            [
                float(by_policy[policy][seed]["heldout_usable_success_q25"])
                - float(by_policy[reference][seed]["heldout_usable_success_q25"])
                for seed in common
            ],
            dtype=float,
        )
        reference_values = np.asarray(
            [float(by_policy[reference][seed]["heldout_usable_success_q25"]) for seed in common],
            dtype=float,
        )
        relative = primary / np.maximum(np.abs(reference_values), 1e-15)
        fidelity = np.asarray(
            [
                float(by_policy[policy][seed]["heldout_conditional_truth_fidelity_mean"])
                - float(by_policy[reference][seed]["heldout_conditional_truth_fidelity_mean"])
                for seed in common
            ],
            dtype=float,
        )
        n = len(common)
        sd = float(np.std(primary, ddof=1)) if n > 1 else 0.0
        half_width = 1.96 * sd / math.sqrt(n) if n else float("nan")
        mean_difference = float(np.mean(primary)) if n else float("nan")
        rows.append(
            {
                "policy": policy,
                "reference": reference,
                "n_paired_seeds": n,
                "wins": int(np.sum(primary > 0)),
                "ties": int(np.sum(np.isclose(primary, 0.0, atol=1e-15))),
                "mean_difference_heldout_usable_success_q25": mean_difference,
                "sd_paired_difference": sd,
                "normal_approx_ci95_low": mean_difference - half_width,
                "normal_approx_ci95_high": mean_difference + half_width,
                "mean_relative_improvement": float(np.mean(relative)) if n else float("nan"),
                "mean_difference_conditional_truth_fidelity": float(np.mean(fidelity)) if n else float("nan"),
                "inference_label": "descriptive_pilot_not_confirmatory",
            }
        )
    return rows


def _discovery_gate(
    config: dict[str, Any],
    comparisons: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    tomography_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    spec = config.get("gate", {})
    target = str(spec.get("policy", "bads"))
    min_wins = int(spec.get("min_wins", math.ceil(0.75 * len(config["seeds"]))))
    min_relative = float(spec.get("min_relative_improvement", 0.10))
    fidelity_margin = float(spec.get("max_conditional_fidelity_decline", 0.01))
    required_references = [name for name in ("catalog", "random") if name in config["policies"]]
    relevant = {
        row["reference"]: row
        for row in comparisons
        if row["policy"] == target and row["reference"] in required_references
    }
    checks: dict[str, Any] = {}
    for reference in required_references:
        row = relevant.get(reference)
        checks[reference] = {
            "available": row is not None,
            "wins": None if row is None else row["wins"],
            "wins_required": min_wins,
            "wins_pass": bool(row is not None and int(row["wins"]) >= min_wins),
            "mean_relative_improvement": None if row is None else row["mean_relative_improvement"],
            "relative_required": min_relative,
            "relative_pass": bool(
                row is not None and float(row["mean_relative_improvement"]) >= min_relative
            ),
            "conditional_fidelity_difference": None
            if row is None
            else row["mean_difference_conditional_truth_fidelity"],
            "fidelity_noninferiority_margin": fidelity_margin,
            "fidelity_pass": bool(
                row is not None
                and float(row["mean_difference_conditional_truth_fidelity"]) >= -fidelity_margin
            ),
        }
    quantitative = bool(checks) and all(
        item["wins_pass"] and item["relative_pass"] and item["fidelity_pass"]
        for item in checks.values()
    )
    by_policy = {
        policy: {int(row["seed"]): row for row in summary if row["policy"] == policy}
        for policy in config["policies"]
    }
    reversal_checks: dict[str, Any] = {}
    stable_reversal = False
    for reference in required_references:
        common = sorted(set(by_policy.get(target, {})) & set(by_policy.get(reference, {})))
        positive_to_negative = 0
        negative_to_positive = 0
        for seed in common:
            target_row = by_policy[target][seed]
            reference_row = by_policy[reference][seed]
            train_difference = float(target_row["train_usable_success_q25"]) - float(
                reference_row["train_usable_success_q25"]
            )
            heldout_difference = float(target_row["heldout_usable_success_q25"]) - float(
                reference_row["heldout_usable_success_q25"]
            )
            positive_to_negative += int(train_difference > 0 and heldout_difference < 0)
            negative_to_positive += int(train_difference < 0 and heldout_difference > 0)
        required = int(spec.get("stable_reversal_min_seeds", min_wins))
        reference_stable = max(positive_to_negative, negative_to_positive) >= required
        stable_reversal = stable_reversal or reference_stable
        reversal_checks[reference] = {
            "train_positive_heldout_negative": positive_to_negative,
            "train_negative_heldout_positive": negative_to_positive,
            "required_same_direction_reversals": required,
            "stable_reversal": reference_stable,
        }

    completed_tomography = [
        row for row in tomography_rows if row.get("tomography_status") == "completed"
    ]
    target_tomography = [row for row in completed_tomography if row["policy"] == target]
    tomography_enabled = bool(config.get("process_tomography", {}).get("enabled", False))
    min_process_fidelity = float(spec.get("min_process_fidelity", 0.90))
    target_mean_process_fidelity = (
        float(np.mean([float(row["average_gate_fidelity"]) for row in target_tomography]))
        if target_tomography
        else None
    )
    process_reference_checks: dict[str, Any] = {}
    for reference in required_references:
        reference_rows = [row for row in completed_tomography if row["policy"] == reference]
        reference_mean = (
            float(np.mean([float(row["average_gate_fidelity"]) for row in reference_rows]))
            if reference_rows
            else None
        )
        difference = (
            None
            if target_mean_process_fidelity is None or reference_mean is None
            else target_mean_process_fidelity - reference_mean
        )
        process_reference_checks[reference] = {
            "reference_mean_process_fidelity": reference_mean,
            "target_minus_reference": difference,
            "noninferiority_margin": fidelity_margin,
            "pass": bool(difference is not None and difference >= -fidelity_margin),
        }
    coherence = bool(
        tomography_enabled
        and len(target_tomography) == len(config["seeds"])
        and target_mean_process_fidelity is not None
        and target_mean_process_fidelity >= min_process_fidelity
        and all(item["pass"] for item in process_reference_checks.values())
    )
    outcome_class = "A" if quantitative else "B" if stable_reversal else "C"
    return {
        "gate_version": "v2-pilot-1",
        "primary_metric": "heldout_usable_success_q25",
        "target_policy": target,
        "paired_checks": checks,
        "quantitative_signal_pass": quantitative,
        "coherent_process_tomography": {
            "role": "diagnostic_not_outcome_gate",
            "enabled": tomography_enabled,
            "completed_finalists": len(completed_tomography),
            "expected_finalists": len(config["seeds"]) * len(config["policies"]),
            "target_completed": len(target_tomography),
            "target_mean_average_gate_fidelity": target_mean_process_fidelity,
            "minimum_mean_average_gate_fidelity": min_process_fidelity,
            "reference_checks": process_reference_checks,
        },
        "coherence_check_pass": coherence,
        "ranking_reversal_checks": reversal_checks,
        "stable_train_heldout_ranking_reversal": stable_reversal,
        "outcome_class": outcome_class,
        "outcome_definition": {
            "A": "all three preregistered quantitative improvement checks pass",
            "B": "stable same-direction train/heldout ranking reversal (mechanism crossover)",
            "C": "neither A nor B; reproducible null/negative pilot",
        },
        "predeclared_A_gate_pass": quantitative,
        "discovery_claim_pass": False,
        "claim_boundary": (
            "Fixed-topology robust calibration pilot only. Simulated Perceval tomography "
            "checks coherence for the modeled process but does not establish a novel gate "
            "or hardware performance."
        ),
    }


def _git_state(root: Path) -> tuple[str, bool]:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=root, text=True
    )
    return commit, bool(status.strip())


def _learning_rows(results: list[tuple[int, PolicyResult]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed, result in results:
        best = -float("inf")
        for observation in result.observations:
            best = max(best, observation.robust_score)
            rows.append(
                {
                    "seed": seed,
                    "policy": result.policy,
                    "query_number": observation.query_number,
                    "candidate_index": observation.candidate_index,
                    "observed_usable_success_q25": observation.usable_success_q25,
                    "best_so_far_usable_success_q25": best,
                }
            )
    return rows


def _save_learning_plot(path: Path, rows: list[dict[str, Any]], policies: list[str]) -> None:
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["policy"]), int(row["query_number"]))].append(
            float(row["best_so_far_usable_success_q25"])
        )
    figure, axis = plt.subplots(figsize=(6.4, 4.2))
    for policy in policies:
        x = sorted(number for name, number in grouped if name == policy)
        if not x:
            continue
        y = [float(np.mean(grouped[(policy, number)])) for number in x]
        axis.plot(x, y, marker="o", markersize=2.5, linewidth=1.4, label=policy)
    axis.set_xlabel("Train oracle queries")
    axis.set_ylabel("Mean best-so-far usable success q25")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=160, metadata={"Software": "QuantumOpt-Explorer"})
    plt.close(figure)
    _atomic_write(path, buffer.getvalue())


def _save_tradeoff_plot(path: Path, summary: list[dict[str, Any]], policies: list[str]) -> None:
    figure, axis = plt.subplots(figsize=(6.0, 4.4))
    for policy in policies:
        selected = [row for row in summary if row["policy"] == policy]
        if not selected:
            continue
        x = np.asarray([row["heldout_usable_success_q25"] for row in selected], dtype=float)
        y = np.asarray(
            [row["heldout_conditional_truth_fidelity_mean"] for row in selected], dtype=float
        )
        axis.scatter(float(np.mean(x)), float(np.mean(y)), s=42, label=policy)
    axis.set_xlabel("Held-out usable success q25")
    axis.set_ylabel("Held-out conditional truth fidelity mean")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=160, metadata={"Software": "QuantumOpt-Explorer"})
    plt.close(figure)
    _atomic_write(path, buffer.getvalue())


def run_experiment(config: dict[str, Any], output: Path) -> dict[str, Any]:
    """Run the frozen experiment and atomically replace only owned artifacts."""
    validate_config(config)
    # Capture provenance before creating or replacing owned outputs. Otherwise a
    # clean checkout is incorrectly reported as dirty solely because runs/v2 is
    # generated by this function.
    source_commit, source_dirty = _git_state(Path(__file__).resolve().parents[2])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    policies = [str(value) for value in config["policies"]]
    seeds = [int(value) for value in config["seeds"]]
    config_digest = config_hash(config)
    protocol_digest = protocol_hash(config)

    query_rows: list[dict[str, Any]] = []
    operational_rows: list[dict[str, Any]] = []
    heldout_rows: list[dict[str, Any]] = []
    freeze_rows: list[dict[str, Any]] = []
    noise_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    policy_results: list[tuple[int, PolicyResult]] = []
    oracle_rows: list[dict[str, Any]] = []
    tomography_rows: list[dict[str, Any]] = []
    tomography_json_rows: list[dict[str, Any]] = []
    tomography_spec = config.get("process_tomography", {})
    tomography_enabled = bool(tomography_spec.get("enabled", False))
    tomography_draw_index = int(tomography_spec.get("heldout_draw_index", 0))

    for seed in seeds:
        captured_seed_artifacts = False
        seed_records: list[tuple[PolicyResult, CalibrationEnvironment]] = []
        for policy in policies:
            env = CalibrationEnvironment(config)
            env.reset(seed)
            result = run_policy(policy, env)
            seed_records.append((result, env))
            policy_results.append((seed, result))
            summary_rows.append(_summary_row(seed, result, env))
            for event in env.events:
                if event["event"] == "query":
                    query_rows.append({"policy": policy, **event})
                elif event["event"] == "freeze":
                    freeze_rows.append({"policy": policy, **event})
                elif event["event"] == "heldout_evaluation":
                    heldout_rows.append({"policy": policy, **event})
            operational_rows.extend({"policy": policy, **event} for event in env.operational_events)
            if not captured_seed_artifacts:
                noise_rows.extend(env.noise_schedule_rows())
                for index, vector in enumerate(env.candidates):
                    candidate_rows.append(
                        {
                            "seed": seed,
                            "candidate_index": index,
                            "candidate_id": candidate_id(vector),
                            **{f"compensation_{i}": float(value) for i, value in enumerate(vector)},
                        }
                    )
                captured_seed_artifacts = True

        # Context-only oracle: all policies have already frozen and received
        # their one finalist held-out evaluation before this exhaustive pass.
        oracle_env = seed_records[-1][1]
        seed_oracle_rows: list[dict[str, Any]] = []
        for candidate_index in range(len(oracle_env.candidates)):
            observation = oracle_env.evaluate_heldout_context(candidate_index)
            row = {
                "seed": seed,
                "context_only": True,
                "available_to_policy": False,
                **observation.to_dict(),
            }
            seed_oracle_rows.append(row)
            oracle_rows.append(row)
        oracle_best = max(
            seed_oracle_rows,
            key=lambda row: (float(row["usable_success_q25"]), -int(row["candidate_index"])),
        )
        for row in summary_rows:
            if int(row["seed"]) != seed:
                continue
            row["heldout_oracle_candidate_index"] = int(oracle_best["candidate_index"])
            row["heldout_oracle_candidate_id"] = oracle_best["candidate_id"]
            row["heldout_oracle_usable_success_q25"] = float(
                oracle_best["usable_success_q25"]
            )
            row["heldout_regret_q25"] = max(
                0.0,
                float(oracle_best["usable_success_q25"])
                - float(row["heldout_usable_success_q25"]),
            )

        for result, env in seed_records:
            base = {
                "seed": seed,
                "policy": result.policy,
                "selected_candidate_index": result.selected_candidate_index,
                "selected_candidate_id": result.selected_train_observation.candidate_id,
                "heldout_draw_index": tomography_draw_index,
            }
            if tomography_enabled:
                tomography = process_tomography(
                    env.candidate(result.selected_candidate_index),
                    env.heldout_noise_draw(tomography_draw_index),
                )
                scalar = {
                    **base,
                    "tomography_status": "completed",
                    **tomography.to_dict(include_matrix=False),
                }
                tomography_rows.append(scalar)
                tomography_json_rows.append(
                    {
                        **scalar,
                        **{
                            key: value
                            for key, value in tomography.to_dict(include_matrix=True).items()
                            if key in {"chi_real", "chi_imag"}
                        },
                    }
                )
            else:
                disabled = {
                    **base,
                    "tomography_status": "disabled_by_config",
                    "average_gate_fidelity": "",
                    "gate_efficiency": "",
                    "chi_trace_real": "",
                    "chi_trace_imag": "",
                    "chi_hermiticity_residual": "",
                }
                tomography_rows.append(disabled)
                tomography_json_rows.append(disabled.copy())

    summary_rows.sort(key=lambda row: (int(row["seed"]), policies.index(str(row["policy"]))))
    query_rows.sort(
        key=lambda row: (
            int(row["seed"]),
            policies.index(str(row["policy"])),
            int(row["query_number"]),
        )
    )
    heldout_rows.sort(key=lambda row: (int(row["seed"]), policies.index(str(row["policy"]))))
    freeze_rows.sort(key=lambda row: (int(row["seed"]), policies.index(str(row["policy"]))))
    comparisons = _comparison_rows(summary_rows, policies)
    learning = _learning_rows(policy_results)
    gate = _discovery_gate(config, comparisons, summary_rows, tomography_rows)

    _write_csv(output / "summary.csv", summary_rows)
    _write_csv(output / "comparisons.csv", comparisons)
    _write_csv(output / "statistical_comparisons.csv", comparisons)
    _write_jsonl(output / "query_log.jsonl", query_rows)
    _write_jsonl(output / "operational_log.jsonl", operational_rows)
    _write_jsonl(output / "heldout_results.jsonl", heldout_rows)
    _write_jsonl(output / "freeze_log.jsonl", freeze_rows)
    _write_csv(output / "noise_schedule.csv", noise_rows)
    _write_csv(output / "candidate_pool.csv", candidate_rows)
    _write_csv(output / "postsearch_oracle.csv", oracle_rows)
    _write_csv(output / "process_tomography.csv", tomography_rows)
    _write_jsonl(output / "process_tomography.jsonl", tomography_json_rows)
    _write_csv(output / "learning_curves.csv", learning)
    _write_json(output / "discovery_gate.json", gate)
    _save_learning_plot(output / "learning_curves.png", learning, policies)
    _save_tradeoff_plot(output / "heldout_tradeoff.png", summary_rows, policies)

    golden = {
        "schema_version": 1,
        "config_hash": config_digest,
        "protocol_hash": protocol_digest,
        "summary_rows": len(summary_rows),
        "query_rows": len(query_rows),
        "primary_metric": "heldout_usable_success_q25",
        "summary_sha256": _sha256(output / "summary.csv"),
        "comparisons_sha256": _sha256(output / "comparisons.csv"),
        "query_log_semantic_sha256": _semantic_query_hash(output / "query_log.jsonl"),
        "postsearch_oracle_sha256": _sha256(output / "postsearch_oracle.csv"),
        "process_tomography_sha256": _sha256(output / "process_tomography.csv"),
    }
    _write_json(output / "golden_summary.json", golden)
    artifact_hashes = {
        name: _sha256(output / name)
        for name in ARTIFACT_NAMES
        if (output / name).is_file()
    }
    manifest = {
        "schema_version": 1,
        "config_hash": config_digest,
        "protocol_hash": protocol_digest,
        "protocol_version": config["protocol_version"],
        "primary_metric": "heldout_usable_success_q25",
        "git_commit": source_commit,
        "git_dirty": source_dirty,
        "git_state_capture_point": "before_output_directory_creation",
        "python_version": platform.python_version(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "numpy_version": np.__version__,
        "matplotlib_version": matplotlib.__version__,
        "perceval_version": pcvl.__version__,
        "seeds": seeds,
        "policies": policies,
        "budget_and_scale": {
            "device_seeds": len(seeds),
            "candidate_pool_size_per_seed": int(config["candidate_pool_size"]),
            "search_query_budget_per_policy": int(config["query_budget"]),
            "shared_warmup_queries": int(config["warmup_queries"]),
            "train_noise_draws_per_query": int(config["train_draws"]),
            "heldout_noise_draws_per_finalist": int(config["heldout_draws"]),
            "logical_inputs_per_draw": 4,
            "postsearch_exhaustive_candidates_per_seed": int(config["candidate_pool_size"]),
            "process_tomography_finalists": len(tomography_rows)
            if tomography_enabled
            else 0,
        },
        "operational_log_is_nondeterministic": True,
        "artifact_sha256": artifact_hashes,
    }
    _write_json(output / "run_manifest.json", manifest)
    return {"output": str(output), "manifest": manifest, "gate": gate}


def verify_run(run_directory: Path, golden_path: Path) -> dict[str, Any]:
    """Verify hashes, the external golden summary, and the no-leak query log."""
    run_directory = Path(run_directory)
    golden_path = Path(golden_path)
    manifest = json.loads((run_directory / "run_manifest.json").read_text(encoding="utf-8"))
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    for name, expected in manifest["artifact_sha256"].items():
        path = run_directory / name
        if not path.is_file():
            raise ValueError(f"missing artifact for hash verification: {name}")
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(f"artifact hash mismatch: {name}")

    actual_golden = {
        "config_hash": manifest["config_hash"],
        "protocol_hash": manifest["protocol_hash"],
        "primary_metric": manifest["primary_metric"],
        "summary_sha256": _sha256(run_directory / "summary.csv"),
        "comparisons_sha256": _sha256(run_directory / "comparisons.csv"),
        "query_log_semantic_sha256": _semantic_query_hash(run_directory / "query_log.jsonl"),
        "postsearch_oracle_sha256": _sha256(run_directory / "postsearch_oracle.csv"),
        "process_tomography_sha256": _sha256(run_directory / "process_tomography.csv"),
    }
    for key, actual in actual_golden.items():
        if key not in golden:
            raise ValueError(f"golden summary is missing key: {key}")
        if golden[key] != actual:
            raise ValueError(f"golden hash or protocol mismatch: {key}")

    query_rows = [
        json.loads(line)
        for line in (run_directory / "query_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    for row in query_rows:
        serialized = canonical_json(row).lower()
        if row.get("event") != "query" or row.get("split") != "train" or "heldout" in serialized:
            raise ValueError("query log violates the no-heldout-leakage contract")
    if "query_rows" in golden and len(query_rows) != int(golden["query_rows"]):
        raise ValueError("query row count mismatch")

    return {
        "verified": True,
        "run": str(run_directory),
        "golden": str(golden_path),
        "artifacts_verified": len(manifest["artifact_sha256"]),
        "query_rows_verified": len(query_rows),
        "config_hash": manifest["config_hash"],
        "protocol_hash": manifest["protocol_hash"],
    }
