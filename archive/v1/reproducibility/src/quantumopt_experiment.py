#!/usr/bin/env python3
"""Run the frozen QuantumOpt-Explorer preliminary experiment.

Perceval constructs every optical layer and supplies its ideal unitary.  The
disclosed NumPy layer applies diagonal amplitude transmission between ideal
layers so that loss schedules can be frozen, inspected, and replayed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import perceval as pcvl


THETA_VALUES = np.array(
    [np.pi / 12, np.pi / 8, np.pi / 6, np.pi / 4, np.pi / 3, 3 * np.pi / 8, 5 * np.pi / 12],
    dtype=float,
)
PHASE_VALUES = np.arange(16, dtype=float) * (2 * np.pi / 16)
POLICY_LABELS = {
    "random": "Random",
    "greedy": "Greedy",
    "bads": "Budget-Aware Diversity Search",
}


@dataclass(frozen=True)
class LayerGene:
    pattern: int
    theta_indices: tuple[int, int]
    phase_indices: tuple[int, int, int, int]


@dataclass(frozen=True)
class Candidate:
    depth: int
    layers: tuple[LayerGene, ...]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_candidate(candidate: Candidate) -> dict[str, Any]:
    return {
        "depth": candidate.depth,
        "layers": [
            {
                "pattern": layer.pattern,
                "theta_indices": list(layer.theta_indices),
                "phase_indices": list(layer.phase_indices),
            }
            for layer in candidate.layers
        ],
    }


def candidate_id(candidate: Candidate) -> str:
    payload = json.dumps(canonical_candidate(candidate), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def teacher_candidate(max_depth: int) -> Candidate:
    if max_depth != 5:
        raise ValueError("The frozen calibration target requires max_depth=5")
    patterns = [0, 1, 0, 1, 0]
    theta = [(3, 4), (2, 0), (5, 2), (4, 0), (1, 5)]
    phases = [
        (0, 2, 5, 7),
        (3, 0, 11, 0),
        (1, 6, 0, 12),
        (8, 2, 13, 5),
        (0, 7, 4, 14),
    ]
    return Candidate(
        depth=max_depth,
        layers=tuple(
            LayerGene(patterns[i], tuple(theta[i]), tuple(phases[i])) for i in range(max_depth)
        ),
    )


def component_count(candidate: Candidate) -> int:
    total = 0
    for layer in candidate.layers[: candidate.depth]:
        total += 2 if layer.pattern == 0 else 1
        total += sum(index != 0 for index in layer.phase_indices)
    return int(total)


def candidate_distance_from_teacher(candidate: Candidate, teacher: Candidate) -> int:
    distance = int(candidate.depth != teacher.depth)
    for left, right in zip(candidate.layers, teacher.layers):
        distance += int(left.pattern != right.pattern)
        distance += sum(a != b for a, b in zip(left.theta_indices, right.theta_indices))
        distance += sum(a != b for a, b in zip(left.phase_indices, right.phase_indices))
    return int(distance)


def _mutate_index(rng: np.random.Generator, value: int, modulus: int) -> int:
    if rng.random() < 0.82:
        delta = int(rng.choice(np.array([-3, -2, -1, 1, 2, 3])))
        return int((value + delta) % modulus)
    return int(rng.integers(0, modulus))


def generate_candidate_pool(
    seed: int, config: dict[str, Any]
) -> tuple[list[Candidate], list[dict[str, float | int]]]:
    """Generate one frozen finite corpus around the disclosed calibration circuit."""
    rng = np.random.default_rng(int(config["pool_seed_offset"]) + seed)
    target_gene = teacher_candidate(int(config["max_depth"]))
    pool: list[Candidate] = []
    provenance: list[dict[str, float | int]] = []
    seen: set[str] = {candidate_id(target_gene)}
    attempts = 0
    while len(pool) < int(config["candidate_pool_size"]):
        attempts += 1
        if attempts > int(config["candidate_pool_size"]) * 1000:
            raise RuntimeError("Unable to generate the requested number of unique candidates")
        mutation_rate = float(rng.uniform(0.05, 0.78))
        depth = int(rng.choice(np.array([3, 4, 5]), p=np.array([0.18, 0.30, 0.52])))
        layers: list[LayerGene] = []
        mutation_events = 0
        for base in target_gene.layers:
            pattern = base.pattern
            if rng.random() < mutation_rate * 0.35:
                pattern = 1 - pattern
                mutation_events += 1
            theta_indices = list(base.theta_indices)
            for index in range(2):
                if rng.random() < mutation_rate:
                    theta_indices[index] = _mutate_index(
                        rng, theta_indices[index], len(THETA_VALUES)
                    )
                    mutation_events += 1
            phase_indices = list(base.phase_indices)
            for index in range(4):
                if rng.random() < mutation_rate:
                    phase_indices[index] = _mutate_index(
                        rng, phase_indices[index], len(PHASE_VALUES)
                    )
                    mutation_events += 1
            layers.append(
                LayerGene(pattern, tuple(theta_indices), tuple(phase_indices))
            )
        if mutation_events == 0 and depth == target_gene.depth:
            continue
        candidate = Candidate(depth=depth, layers=tuple(layers))
        if component_count(candidate) > int(config["max_components"]):
            continue
        cid = candidate_id(candidate)
        if cid in seen:
            continue
        seen.add(cid)
        pool.append(candidate)
        provenance.append(
            {
                "generation_mutation_rate": mutation_rate,
                "generation_mutation_events": mutation_events,
                "hamming_distance_from_teacher": candidate_distance_from_teacher(
                    candidate, target_gene
                ),
            }
        )
    return pool, provenance


def candidate_feature(candidate: Candidate, config: dict[str, Any]) -> np.ndarray:
    """Encode only observable circuit genes; no score or held-out value is included."""
    max_depth = int(config["max_depth"])
    values: list[float] = [
        candidate.depth / max_depth,
        component_count(candidate) / int(config["max_components"]),
    ]
    for layer_index in range(max_depth):
        layer = candidate.layers[layer_index]
        active = float(layer_index < candidate.depth)
        values.extend([active, active * (2 * layer.pattern - 1)])
        for index in layer.theta_indices:
            values.append(active * index / (len(THETA_VALUES) - 1))
        for index in layer.phase_indices:
            angle = float(PHASE_VALUES[index])
            values.extend([active * math.sin(angle), active * math.cos(angle)])
    return np.asarray(values, dtype=float)


def layer_matrix(layer: LayerGene, modes: int) -> np.ndarray:
    """Construct a layer with official Perceval components and return its unitary."""
    circuit = pcvl.Circuit(modes)
    pairs = [(0, 1), (2, 3)] if layer.pattern == 0 else [(1, 2)]
    for slot, (first_mode, _second_mode) in enumerate(pairs):
        theta = float(THETA_VALUES[layer.theta_indices[slot]])
        circuit.add(first_mode, pcvl.BS(theta=theta))
    for mode, phase_index in enumerate(layer.phase_indices):
        if phase_index:
            circuit.add(mode, pcvl.PS(phi=float(PHASE_VALUES[phase_index])))
    return np.asarray(circuit.compute_unitary(), dtype=complex)


def candidate_layer_matrices(
    candidate: Candidate,
    modes: int,
    cache: dict[LayerGene, np.ndarray] | None = None,
) -> list[np.ndarray]:
    if cache is None:
        cache = {}
    matrices: list[np.ndarray] = []
    for layer in candidate.layers[: candidate.depth]:
        if layer not in cache:
            cache[layer] = layer_matrix(layer, modes)
        matrices.append(cache[layer])
    return matrices


def compose_transfer(
    matrices: Sequence[np.ndarray],
    modes: int,
    loss_pattern: np.ndarray | None = None,
) -> np.ndarray:
    transfer = np.eye(modes, dtype=complex)
    for layer_index, unitary in enumerate(matrices):
        transfer = unitary @ transfer
        if loss_pattern is not None:
            intensity_transmission = 1.0 - loss_pattern[layer_index]
            attenuation = np.diag(np.sqrt(intensity_transmission))
            transfer = attenuation @ transfer
    return transfer


def normalized_process_fidelity(target: np.ndarray, transfer: np.ndarray) -> float:
    numerator = abs(np.trace(target.conj().T @ transfer)) ** 2
    denominator = float(
        np.trace(target.conj().T @ target).real
        * np.trace(transfer.conj().T @ transfer).real
    )
    if denominator <= 0:
        return 0.0
    return float(np.clip(numerator / denominator, 0.0, 1.0))


def mean_single_photon_survival(transfer: np.ndarray, modes: int) -> float:
    value = np.trace(transfer.conj().T @ transfer).real / modes
    return float(np.clip(value, 0.0, 1.0))


def generate_loss_schedule(
    seed: int, split: str, config: dict[str, Any]
) -> np.ndarray:
    if split not in {"train", "heldout"}:
        raise ValueError(f"Unknown split: {split}")
    count = int(config[f"{split}_loss_patterns"])
    spec = config[f"{split}_loss"]
    split_offset = 0 if split == "train" else 1_000_003
    rng = np.random.default_rng(int(config["loss_seed_offset"]) + 10_007 * seed + split_offset)
    common = rng.normal(
        0.0,
        float(spec["common_sigma"]),
        size=(count, int(config["max_depth"]), 1),
    )
    mode_noise = rng.normal(
        0.0,
        float(spec["mode_sigma"]),
        size=(count, int(config["max_depth"]), int(config["modes"])),
    )
    bias = np.asarray(spec["mode_bias"], dtype=float).reshape(1, 1, -1)
    losses = float(spec["mean"]) + common + mode_noise + bias
    return np.clip(losses, float(spec["minimum"]), float(spec["maximum"]))


def summarize_pattern_metrics(
    pattern_rows: Sequence[dict[str, float]],
    candidate: Candidate,
    config: dict[str, Any],
) -> dict[str, float | int]:
    fidelity = np.asarray([row["fidelity"] for row in pattern_rows], dtype=float)
    success = np.asarray([row["success_probability"] for row in pattern_rows], dtype=float)
    count = component_count(candidate)
    compactness = 1.0 - count / int(config["max_components"])
    weights = config["utility_weights"]
    fidelity_q25 = float(np.quantile(fidelity, 0.25))
    success_q25 = float(np.quantile(success, 0.25))
    utility = (
        float(weights["fidelity_q25"]) * fidelity_q25
        + float(weights["success_q25"]) * success_q25
        + float(weights["compactness"]) * compactness
    )
    return {
        "fidelity_q25": fidelity_q25,
        "fidelity_median": float(np.median(fidelity)),
        "fidelity_mean": float(np.mean(fidelity)),
        "success_q25": success_q25,
        "success_median": float(np.median(success)),
        "success_mean": float(np.mean(success)),
        "robust_utility": float(utility),
        "objective_loss": float(1.0 - utility),
        "component_count": count,
        "depth": candidate.depth,
    }


def evaluate_candidate(
    candidate: Candidate,
    target: np.ndarray,
    loss_schedule: np.ndarray,
    config: dict[str, Any],
    layer_cache: dict[LayerGene, np.ndarray] | None = None,
) -> tuple[dict[str, float | int], list[dict[str, float]]]:
    matrices = candidate_layer_matrices(candidate, int(config["modes"]), layer_cache)
    ideal = compose_transfer(matrices, int(config["modes"]))
    ideal_fidelity = normalized_process_fidelity(target, ideal)
    rows: list[dict[str, float]] = []
    for pattern_index, pattern in enumerate(loss_schedule):
        transfer = compose_transfer(matrices, int(config["modes"]), pattern)
        rows.append(
            {
                "pattern_index": float(pattern_index),
                "mean_loss_rate": float(np.mean(pattern[: candidate.depth])),
                "fidelity": normalized_process_fidelity(target, transfer),
                "success_probability": mean_single_photon_survival(
                    transfer, int(config["modes"])
                ),
            }
        )
    summary = summarize_pattern_metrics(rows, candidate, config)
    summary["ideal_fidelity"] = ideal_fidelity
    return summary, rows


def pairwise_distances(features: np.ndarray, reference: np.ndarray) -> np.ndarray:
    delta = features[:, None, :] - reference[None, :, :]
    return np.linalg.norm(delta, axis=2) / math.sqrt(features.shape[1])


def choose_greedy(
    candidates: Sequence[Candidate],
    features: np.ndarray,
    observed_indices: Sequence[int],
    observed_scores: Sequence[float],
) -> tuple[int, dict[str, float | str]]:
    best_observed_position = int(np.argmax(np.asarray(observed_scores)))
    anchor_index = int(observed_indices[best_observed_position])
    observed_set = set(observed_indices)
    available = np.asarray(
        [index for index in range(len(candidates)) if index not in observed_set], dtype=int
    )
    distances = np.linalg.norm(features[available] - features[anchor_index], axis=1)
    order = sorted(
        range(len(available)),
        key=lambda position: (
            float(distances[position]),
            candidate_id(candidates[int(available[position])]),
        ),
    )
    selected = int(available[order[0]])
    return selected, {
        "selection_reason": "nearest_unqueried_to_current_best",
        "anchor_candidate": candidate_id(candidates[anchor_index]),
        "acquisition_value": float(-distances[order[0]]),
    }


def choose_bads(
    candidates: Sequence[Candidate],
    features: np.ndarray,
    observed_indices: Sequence[int],
    observed_scores: Sequence[float],
    step: int,
    config: dict[str, Any],
) -> tuple[int, dict[str, float | str]]:
    observed_set = set(observed_indices)
    available = np.asarray(
        [index for index in range(len(candidates)) if index not in observed_set], dtype=int
    )
    observed = np.asarray(observed_indices, dtype=int)
    distances = pairwise_distances(features[available], features[observed])
    k = min(8, len(observed))
    nearest_order = np.argsort(distances, axis=1)[:, :k]
    nearest_distances = np.take_along_axis(distances, nearest_order, axis=1)
    scores = np.asarray(observed_scores, dtype=float)
    nearest_scores = scores[nearest_order]
    weights = 1.0 / np.maximum(nearest_distances, 1e-6)
    prediction = np.sum(weights * nearest_scores, axis=1) / np.sum(weights, axis=1)
    local_variance = np.sum(
        weights * (nearest_scores - prediction[:, None]) ** 2, axis=1
    ) / np.sum(weights, axis=1)
    uncertainty = np.sqrt(np.maximum(local_variance, 0.0)) + 0.35 * nearest_distances[:, 0]
    elite_count = max(2, int(math.ceil(0.20 * len(observed))))
    elite_positions = np.argsort(scores)[-elite_count:]
    elite = observed[elite_positions]
    elite_distance = np.min(
        pairwise_distances(features[available], features[elite]), axis=1
    )
    denominator = max(1, int(config["query_budget"]) - int(config["warmup_queries"]) - 1)
    progress = np.clip(
        (step - int(config["warmup_queries"])) / denominator, 0.0, 1.0
    )
    exploration_weight = 0.34 * (1.0 - progress) + 0.05
    diversity_weight = 0.22 * (1.0 - progress) + 0.03
    acquisition = (
        prediction
        + exploration_weight * uncertainty
        + diversity_weight * elite_distance
    )
    order = sorted(
        range(len(available)),
        key=lambda position: (
            -float(acquisition[position]),
            candidate_id(candidates[int(available[position])]),
        ),
    )
    selected_position = order[0]
    selected = int(available[selected_position])
    return selected, {
        "selection_reason": "annealed_knn_utility_plus_uncertainty_and_elite_diversity",
        "predicted_utility": float(prediction[selected_position]),
        "estimated_uncertainty": float(uncertainty[selected_position]),
        "elite_distance": float(elite_distance[selected_position]),
        "exploration_weight": float(exploration_weight),
        "diversity_weight": float(diversity_weight),
        "acquisition_value": float(acquisition[selected_position]),
    }


def pareto_front_indices(
    rows: Sequence[dict[str, Any]], indices: Sequence[int]
) -> list[int]:
    front: list[int] = []
    for index in indices:
        item = rows[index]
        dominated = False
        for other_index in indices:
            if other_index == index:
                continue
            other = rows[other_index]
            no_worse = (
                other["fidelity_q25"] >= item["fidelity_q25"]
                and other["success_q25"] >= item["success_q25"]
                and other["component_count"] <= item["component_count"]
            )
            strictly_better = (
                other["fidelity_q25"] > item["fidelity_q25"]
                or other["success_q25"] > item["success_q25"]
                or other["component_count"] < item["component_count"]
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(index)
    return sorted(front)


def json_ready(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(json_ready(row), sort_keys=True) + "\n")


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write an empty CSV: {path}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(json_ready(row))


def bootstrap_mean_interval(
    values: np.ndarray, resamples: int, seed: int
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(resamples, len(values)), replace=True)
    means = np.mean(draws, axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def stable_seed(label: str) -> int:
    return int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def run_experiment(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    query_pattern_rows: list[dict[str, Any]] = []
    final_pattern_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    learning_rows: list[dict[str, Any]] = []
    pareto_rows: list[dict[str, Any]] = []

    modes = int(config["modes"])
    teacher = teacher_candidate(int(config["max_depth"]))
    shared_layer_cache: dict[LayerGene, np.ndarray] = {}
    target = compose_transfer(
        candidate_layer_matrices(teacher, modes, shared_layer_cache), modes
    )

    for seed in config["episode_seeds"]:
        seed = int(seed)
        pool, provenance = generate_candidate_pool(seed, config)
        features = np.vstack([candidate_feature(candidate, config) for candidate in pool])
        for pool_index, (candidate, source) in enumerate(zip(pool, provenance)):
            candidate_rows.append(
                {
                    "episode_seed": seed,
                    "pool_index": pool_index,
                    "candidate_id": candidate_id(candidate),
                    "component_count": component_count(candidate),
                    "design": canonical_candidate(candidate),
                    **source,
                }
            )

        schedules = {
            split: generate_loss_schedule(seed, split, config)
            for split in ("train", "heldout")
        }
        for split, schedule in schedules.items():
            for pattern_index, pattern in enumerate(schedule):
                for layer_index in range(pattern.shape[0]):
                    for mode in range(pattern.shape[1]):
                        loss_rows.append(
                            {
                                "episode_seed": seed,
                                "split": split,
                                "pattern_index": pattern_index,
                                "layer_index": layer_index,
                                "mode": mode,
                                "intensity_loss_rate": float(pattern[layer_index, mode]),
                            }
                        )

        training_cache: dict[int, tuple[dict[str, Any], list[dict[str, float]]]] = {}
        heldout_cache: dict[int, tuple[dict[str, Any], list[dict[str, float]]]] = {}

        def evaluate(index: int, split: str) -> tuple[dict[str, Any], list[dict[str, float]]]:
            cache = training_cache if split == "train" else heldout_cache
            if index not in cache:
                cache[index] = evaluate_candidate(
                    pool[index],
                    target,
                    schedules[split],
                    config,
                    shared_layer_cache,
                )
            return cache[index]

        common_order = np.random.default_rng(
            int(config["policy_seed_offset"]) + seed
        ).permutation(len(pool))
        warmup = [int(index) for index in common_order[: int(config["warmup_queries"])] ]

        for policy in config["policies"]:
            observed_indices: list[int] = []
            observed_scores: list[float] = []
            policy_candidate_metrics: dict[int, dict[str, Any]] = {}
            best_so_far = -np.inf
            for step in range(int(config["query_budget"])):
                if step < int(config["warmup_queries"]):
                    selected = warmup[step]
                    acquisition: dict[str, Any] = {
                        "selection_reason": "shared_frozen_warmup",
                        "acquisition_value": None,
                    }
                elif policy == "random":
                    observed_set = set(observed_indices)
                    selected = next(
                        int(index) for index in common_order if int(index) not in observed_set
                    )
                    acquisition = {
                        "selection_reason": "frozen_uniform_random_order",
                        "acquisition_value": None,
                    }
                elif policy == "greedy":
                    selected, acquisition = choose_greedy(
                        pool, features, observed_indices, observed_scores
                    )
                elif policy == "bads":
                    selected, acquisition = choose_bads(
                        pool,
                        features,
                        observed_indices,
                        observed_scores,
                        step,
                        config,
                    )
                else:
                    raise ValueError(f"Unknown policy: {policy}")

                summary, pattern_metrics = evaluate(selected, "train")
                observed_indices.append(selected)
                observed_scores.append(float(summary["robust_utility"]))
                policy_candidate_metrics[selected] = summary
                best_so_far = max(best_so_far, float(summary["robust_utility"]))
                cid = candidate_id(pool[selected])
                query_rows.append(
                    {
                        "episode_seed": seed,
                        "policy": policy,
                        "step": step,
                        "query_budget": int(config["query_budget"]),
                        "budget_remaining_after_query": int(config["query_budget"]) - step - 1,
                        "split_visible_to_policy": "train",
                        "candidate_id": cid,
                        "pool_index": selected,
                        **summary,
                        "best_utility_so_far": best_so_far,
                        **acquisition,
                    }
                )
                learning_rows.append(
                    {
                        "episode_seed": seed,
                        "policy": policy,
                        "step": step,
                        "best_utility_so_far": best_so_far,
                    }
                )
                for pattern_row in pattern_metrics:
                    query_pattern_rows.append(
                        {
                            "episode_seed": seed,
                            "policy": policy,
                            "step": step,
                            "candidate_id": cid,
                            "split": "train",
                            **pattern_row,
                        }
                    )

            selected_position = int(np.argmax(np.asarray(observed_scores)))
            primary_index = observed_indices[selected_position]
            train_primary = policy_candidate_metrics[primary_index]
            indexed_metrics = [dict() for _ in pool]
            for index, summary in policy_candidate_metrics.items():
                indexed_metrics[index] = summary
            front = pareto_front_indices(indexed_metrics, observed_indices)
            # Both the primary candidate and the complete training-defined Pareto
            # archive are frozen before any held-out evaluation is requested.
            heldout_primary, _ = evaluate(primary_index, "heldout")
            auc = float(
                np.mean(
                    [
                        row["best_utility_so_far"]
                        for row in learning_rows
                        if row["episode_seed"] == seed and row["policy"] == policy
                    ]
                )
            )
            episode_rows.append(
                {
                    "episode_seed": seed,
                    "policy": policy,
                    "selected_candidate_id": candidate_id(pool[primary_index]),
                    "query_budget": int(config["query_budget"]),
                    "unique_queries": len(set(observed_indices)),
                    "search_auc": auc,
                    "depth": pool[primary_index].depth,
                    "component_count": component_count(pool[primary_index]),
                    "train_fidelity_q25": train_primary["fidelity_q25"],
                    "train_success_q25": train_primary["success_q25"],
                    "train_robust_utility": train_primary["robust_utility"],
                    "train_objective_loss": train_primary["objective_loss"],
                    "heldout_fidelity_q25": heldout_primary["fidelity_q25"],
                    "heldout_success_q25": heldout_primary["success_q25"],
                    "heldout_robust_utility": heldout_primary["robust_utility"],
                    "heldout_objective_loss": heldout_primary["objective_loss"],
                    "fidelity_generalization_gap": float(
                        train_primary["fidelity_q25"] - heldout_primary["fidelity_q25"]
                    ),
                    "success_generalization_gap": float(
                        train_primary["success_q25"] - heldout_primary["success_q25"]
                    ),
                }
            )

            for index in front:
                train_summary = policy_candidate_metrics[index]
                heldout_summary, heldout_patterns = evaluate(index, "heldout")
                selected_for_primary = index == primary_index
                pareto_rows.append(
                    {
                        "episode_seed": seed,
                        "policy": policy,
                        "candidate_id": candidate_id(pool[index]),
                        "selected_for_primary": selected_for_primary,
                        "depth": pool[index].depth,
                        "component_count": component_count(pool[index]),
                        "train_fidelity_q25": train_summary["fidelity_q25"],
                        "train_success_q25": train_summary["success_q25"],
                        "train_robust_utility": train_summary["robust_utility"],
                        "heldout_fidelity_q25": heldout_summary["fidelity_q25"],
                        "heldout_success_q25": heldout_summary["success_q25"],
                        "heldout_robust_utility": heldout_summary["robust_utility"],
                    }
                )
                train_patterns = evaluate(index, "train")[1]
                for split, pattern_metrics in (
                    ("train", train_patterns),
                    ("heldout", heldout_patterns),
                ):
                    for pattern_row in pattern_metrics:
                        final_pattern_rows.append(
                            {
                                "episode_seed": seed,
                                "policy": policy,
                                "candidate_id": candidate_id(pool[index]),
                                "selected_for_primary": selected_for_primary,
                                "pareto_archive_member": True,
                                "split": split,
                                **pattern_row,
                            }
                        )

    return {
        "candidate_pool": candidate_rows,
        "loss_schedules": loss_rows,
        "query_log": query_rows,
        "query_pattern_metrics": query_pattern_rows,
        "final_pattern_metrics": final_pattern_rows,
        "episode_summary": episode_rows,
        "learning_curves": learning_rows,
        "pareto_front": pareto_rows,
    }


def aggregate_results(
    episode_rows: Sequence[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    metrics = [
        "search_auc",
        "train_fidelity_q25",
        "train_success_q25",
        "train_robust_utility",
        "train_objective_loss",
        "heldout_fidelity_q25",
        "heldout_success_q25",
        "heldout_robust_utility",
        "heldout_objective_loss",
        "fidelity_generalization_gap",
        "success_generalization_gap",
        "depth",
        "component_count",
    ]
    aggregate_rows: list[dict[str, Any]] = []
    for policy in config["policies"]:
        policy_rows = [row for row in episode_rows if row["policy"] == policy]
        for metric in metrics:
            values = np.asarray([float(row[metric]) for row in policy_rows], dtype=float)
            low, high = bootstrap_mean_interval(
                values,
                int(config["bootstrap_resamples"]),
                stable_seed(f"aggregate:{policy}:{metric}"),
            )
            aggregate_rows.append(
                {
                    "policy": policy,
                    "metric": metric,
                    "n_episodes": len(values),
                    "mean": float(np.mean(values)),
                    "median": float(np.median(values)),
                    "standard_deviation": float(np.std(values, ddof=1)),
                    "q25": float(np.quantile(values, 0.25)),
                    "q75": float(np.quantile(values, 0.75)),
                    "mean_ci95_low": low,
                    "mean_ci95_high": high,
                }
            )

    by_policy_seed = {
        (row["policy"], int(row["episode_seed"])): row for row in episode_rows
    }
    comparison_rows: list[dict[str, Any]] = []
    for baseline in ("random", "greedy"):
        for metric in (
            "heldout_fidelity_q25",
            "heldout_success_q25",
            "heldout_robust_utility",
            "search_auc",
        ):
            differences = np.asarray(
                [
                    float(by_policy_seed[("bads", int(seed))][metric])
                    - float(by_policy_seed[(baseline, int(seed))][metric])
                    for seed in config["episode_seeds"]
                ],
                dtype=float,
            )
            low, high = bootstrap_mean_interval(
                differences,
                int(config["bootstrap_resamples"]),
                stable_seed(f"paired:bads:{baseline}:{metric}"),
            )
            comparison_rows.append(
                {
                    "comparison": f"bads_minus_{baseline}",
                    "baseline": baseline,
                    "metric": metric,
                    "n_paired_episodes": len(differences),
                    "mean_paired_difference": float(np.mean(differences)),
                    "median_paired_difference": float(np.median(differences)),
                    "paired_ci95_low": low,
                    "paired_ci95_high": high,
                    "bads_wins": int(np.sum(differences > 0)),
                    "ties": int(np.sum(np.isclose(differences, 0.0))),
                }
            )

    def comparison(baseline: str, metric: str) -> dict[str, Any]:
        return next(
            row
            for row in comparison_rows
            if row["baseline"] == baseline and row["metric"] == metric
        )

    gate_details: list[dict[str, Any]] = []
    all_pass = True
    for baseline in ("random", "greedy"):
        fidelity = comparison(baseline, "heldout_fidelity_q25")
        success = comparison(baseline, "heldout_success_q25")
        fidelity_pass = (
            float(fidelity["mean_paired_difference"])
            >= float(config["practical_fidelity_margin"])
            and float(fidelity["paired_ci95_low"]) > 0.0
        )
        success_pass = (
            float(success["paired_ci95_low"])
            >= float(config["success_noninferiority_margin"])
        )
        baseline_pass = bool(fidelity_pass and success_pass)
        all_pass = bool(all_pass and baseline_pass)
        gate_details.append(
            {
                "comparison": f"bads_vs_{baseline}",
                "fidelity_practical_margin_required": float(
                    config["practical_fidelity_margin"]
                ),
                "fidelity_mean_difference": fidelity["mean_paired_difference"],
                "fidelity_ci95_low": fidelity["paired_ci95_low"],
                "fidelity_ci95_high": fidelity["paired_ci95_high"],
                "fidelity_condition_pass": fidelity_pass,
                "success_ci95_low": success["paired_ci95_low"],
                "success_noninferiority_margin": float(
                    config["success_noninferiority_margin"]
                ),
                "success_condition_pass": success_pass,
                "comparison_pass": baseline_pass,
            }
        )
    comparison_rows.extend(gate_details)
    return aggregate_rows, comparison_rows, all_pass


def aggregate_lookup(
    rows: Sequence[dict[str, Any]], policy: str, metric: str
) -> dict[str, Any]:
    return next(row for row in rows if row["policy"] == policy and row["metric"] == metric)


def comparison_lookup(
    rows: Sequence[dict[str, Any]], baseline: str, metric: str
) -> dict[str, Any]:
    return next(
        row
        for row in rows
        if row.get("baseline") == baseline and row.get("metric") == metric
    )


def make_figures(
    data: dict[str, list[dict[str, Any]]], output_root: Path, config: dict[str, Any]
) -> None:
    figure_dir = output_root / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    episode_rows = data["episode_summary"]
    colors = {"random": "#7A7A7A", "greedy": "#2B6CB0", "bads": "#15803D"}

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3), constrained_layout=True)
    for axis, metric, title in (
        (axes[0], "heldout_fidelity_q25", "Held-out worst-quartile fidelity"),
        (axes[1], "heldout_success_q25", "Held-out worst-quartile survival"),
    ):
        values = [
            [float(row[metric]) for row in episode_rows if row["policy"] == policy]
            for policy in config["policies"]
        ]
        boxes = axis.boxplot(
            values,
            tick_labels=[POLICY_LABELS[policy] for policy in config["policies"]],
            patch_artist=True,
            widths=0.58,
        )
        for box, policy in zip(boxes["boxes"], config["policies"]):
            box.set_facecolor(colors[policy])
            box.set_alpha(0.72)
        axis.set_title(title)
        axis.set_ylabel("Metric value")
        axis.grid(axis="y", alpha=0.25)
        axis.tick_params(axis="x", rotation=16)
    fig.suptitle("Post-freeze performance across 12 paired episodes", fontsize=13)
    fig.savefig(figure_dir / "heldout_performance.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    for policy in config["policies"]:
        matrix = np.asarray(
            [
                [
                    float(row["best_utility_so_far"])
                    for row in data["learning_curves"]
                    if row["policy"] == policy and row["episode_seed"] == seed
                ]
                for seed in config["episode_seeds"]
            ],
            dtype=float,
        )
        steps = np.arange(matrix.shape[1]) + 1
        mean = np.mean(matrix, axis=0)
        q25 = np.quantile(matrix, 0.25, axis=0)
        q75 = np.quantile(matrix, 0.75, axis=0)
        axis.plot(steps, mean, label=POLICY_LABELS[policy], color=colors[policy], lw=2)
        axis.fill_between(steps, q25, q75, color=colors[policy], alpha=0.15)
    axis.axvline(int(config["warmup_queries"]), color="black", ls="--", lw=1, alpha=0.55)
    axis.text(
        int(config["warmup_queries"]) + 0.5,
        axis.get_ylim()[0],
        "shared warm-up ends",
        fontsize=8,
        va="bottom",
    )
    axis.set_xlabel("Oracle queries consumed")
    axis.set_ylabel("Best training robust utility so far")
    axis.set_title("Equal-budget learning curves (mean and episode IQR)")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    fig.savefig(figure_dir / "learning_curves.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6.4, 5.4), constrained_layout=True)
    for policy in config["policies"]:
        policy_rows = [row for row in episode_rows if row["policy"] == policy]
        axis.scatter(
            [float(row["train_fidelity_q25"]) for row in policy_rows],
            [float(row["heldout_fidelity_q25"]) for row in policy_rows],
            label=POLICY_LABELS[policy],
            color=colors[policy],
            alpha=0.82,
            s=42,
        )
    lower = min(
        min(float(row["train_fidelity_q25"]) for row in episode_rows),
        min(float(row["heldout_fidelity_q25"]) for row in episode_rows),
    )
    upper = max(
        max(float(row["train_fidelity_q25"]) for row in episode_rows),
        max(float(row["heldout_fidelity_q25"]) for row in episode_rows),
    )
    axis.plot([lower, upper], [lower, upper], color="black", ls="--", lw=1)
    axis.set_xlabel("Training loss distribution: fidelity q25")
    axis.set_ylabel("Held-out loss distribution: fidelity q25")
    axis.set_title("Distribution-shift check for training-selected circuits")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    fig.savefig(figure_dir / "train_vs_heldout.png", dpi=180)
    plt.close(fig)

    example_seed = int(config["episode_seeds"][0])
    fig, axis = plt.subplots(figsize=(7.4, 5.2), constrained_layout=True)
    query_by_policy_candidate: dict[tuple[str, str], dict[str, Any]] = {}
    for row in data["query_log"]:
        if int(row["episode_seed"]) == example_seed:
            query_by_policy_candidate[(row["policy"], row["candidate_id"])] = row
    for policy in config["policies"]:
        rows = [
            row
            for (row_policy, _candidate), row in query_by_policy_candidate.items()
            if row_policy == policy
        ]
        axis.scatter(
            [float(row["success_q25"]) for row in rows],
            [float(row["fidelity_q25"]) for row in rows],
            color=colors[policy],
            alpha=0.35,
            s=25,
            label=POLICY_LABELS[policy],
        )
        selected = next(
            row
            for row in episode_rows
            if row["policy"] == policy and int(row["episode_seed"]) == example_seed
        )
        selected_query = query_by_policy_candidate[
            (policy, selected["selected_candidate_id"])
        ]
        axis.scatter(
            [float(selected_query["success_q25"])],
            [float(selected_query["fidelity_q25"])],
            color=colors[policy],
            edgecolor="black",
            marker="*",
            s=170,
        )
    axis.set_xlabel("Training worst-quartile survival")
    axis.set_ylabel("Training worst-quartile fidelity")
    axis.set_title(f"Queried designs and frozen selections (episode seed {example_seed})")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    fig.savefig(figure_dir / "example_search_pareto.png", dpi=180)
    plt.close(fig)


def format_metric(row: dict[str, Any], digits: int = 4) -> str:
    return (
        f"{float(row['mean']):.{digits}f} "
        f"[{float(row['mean_ci95_low']):.{digits}f}, "
        f"{float(row['mean_ci95_high']):.{digits}f}]"
    )


def generate_report(
    output_root: Path,
    config: dict[str, Any],
    aggregate_rows: Sequence[dict[str, Any]],
    comparison_rows: Sequence[dict[str, Any]],
    gate_pass: bool,
) -> None:
    table_lines = []
    for policy in config["policies"]:
        table_lines.append(
            "| {label} | {fidelity} | {success} | {loss} | {auc} |".format(
                label=POLICY_LABELS[policy],
                fidelity=format_metric(
                    aggregate_lookup(aggregate_rows, policy, "heldout_fidelity_q25")
                ),
                success=format_metric(
                    aggregate_lookup(aggregate_rows, policy, "heldout_success_q25")
                ),
                loss=format_metric(
                    aggregate_lookup(aggregate_rows, policy, "heldout_objective_loss")
                ),
                auc=format_metric(aggregate_lookup(aggregate_rows, policy, "search_auc")),
            )
        )

    comparison_lines = []
    for baseline in ("random", "greedy"):
        fidelity = comparison_lookup(
            comparison_rows, baseline, "heldout_fidelity_q25"
        )
        success = comparison_lookup(
            comparison_rows, baseline, "heldout_success_q25"
        )
        comparison_lines.append(
            "| BADS - {baseline} | {fd:.4f} [{fl:.4f}, {fh:.4f}] | "
            "{sd:.4f} [{sl:.4f}, {sh:.4f}] | {wins}/{total} |".format(
                baseline=POLICY_LABELS[baseline],
                fd=float(fidelity["mean_paired_difference"]),
                fl=float(fidelity["paired_ci95_low"]),
                fh=float(fidelity["paired_ci95_high"]),
                sd=float(success["mean_paired_difference"]),
                sl=float(success["paired_ci95_low"]),
                sh=float(success["paired_ci95_high"]),
                wins=int(fidelity["bads_wins"]),
                total=int(fidelity["n_paired_episodes"]),
            )
        )

    status = "PASSED" if gate_pass else "NOT PASSED"
    interpretation = (
        "The preregistered gate passed. This supports a narrow claim that the search policy "
        "improved this finite simulator benchmark; it does not establish a new optical "
        "experiment or hardware robustness."
        if gate_pass
        else "This is a bounded negative result: this version of the acquisition rule has "
        "not shown a reliable, practically sized held-out fidelity advantage over both "
        "simpler policies."
    )
    report = f"""# Preliminary experimental report

## Executive result

The frozen experiment completed {len(config['episode_seeds'])} paired episodes for
three policies, with {config['query_budget']} training-oracle queries per policy and
episode. The preregistered discovery gate **{status}**. {interpretation}

Values below are means with episode-resampled 95% bootstrap confidence intervals in
brackets. `objective loss` is one minus the disclosed scalar utility;
the fidelity and survival columns remain the scientific quantities of interest.

| Policy | Held-out fidelity q25 | Held-out survival q25 | Held-out objective loss | Search AUC |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(table_lines)}

Paired policy differences use the same candidate pool, loss schedules, warm-up,
seeds, and query budget within every episode.

| Comparison | Fidelity difference | Survival difference | Fidelity wins |
| --- | ---: | ---: | ---: |
{chr(10).join(comparison_lines)}

## Question and experiment boundary

The experiment asks whether an adaptive, budget-aware and diversity-seeking policy
can find compact linear-optical circuits that better retain a target transformation
under unseen loss than random or nearest-neighbour greedy search. It is a controlled
calibration benchmark. It does not claim that the fixed target, finite candidate pool,
or returned circuits are scientifically novel.

The target is the lossless transfer matrix of one disclosed five-layer, four-mode
Perceval circuit. Each episode contains {config['candidate_pool_size']} unique valid
candidates generated around that circuit; the exact pool is saved before search. The
three policies share the first {config['warmup_queries']} queries and then consume the
same total budget. Random follows a frozen permutation. Greedy queries the unobserved
design closest to its current best. BADS uses a k-nearest-neighbour prediction plus
annealed uncertainty and elite-distance terms; its exploration pressure falls as the
remaining budget shrinks.

## Optical simulation

Perceval {pcvl.__version__} constructs every beam-splitter and phase-shifter layer and
computes its ideal unitary. After each layer, the harness applies the frozen diagonal
amplitude matrix `diag(sqrt(1 - intensity_loss))`. Training loss has mean
{config['train_loss']['mean']:.3f} before clipping. Held-out loss is stronger,
asymmetric and shifted to mean {config['heldout_loss']['mean']:.3f} plus fixed
mode-specific biases. The exact per-mode, per-layer draws are in
`raw/loss_schedules.csv`.

Normalized process fidelity is the squared Hilbert-Schmidt overlap between the ideal
target and lossy transfer matrix, normalized by both matrix norms. Survival is the
mean single-photon transmission, `Tr(A^dagger A) / 4`. The policy observes the 25th
percentile over 16 training loss patterns. The selected circuit and the training-only
Pareto archive are frozen before evaluation on 24 held-out patterns.

## Discovery gate

The primary gate requires BADS to exceed both baselines by at least
{config['practical_fidelity_margin']:.3f} mean held-out fidelity q25, with the lower
endpoint of each paired 95% bootstrap interval above zero. In addition, the lower
endpoint of the paired survival difference must be at least
{config['success_noninferiority_margin']:.3f}. The result above follows that rule
without changing the threshold after inspection.

## What the traces show

`raw/query_log.jsonl` records every selection reason, observed training metric, budget
remainder and best-so-far utility. `raw/query_pattern_metrics.csv` retains the 16
pattern-level measurements behind every query. `results/learning_curves.csv` and
`figures/learning_curves.png` show query efficiency. The training-defined Pareto sets,
including fidelity, survival and component count, are preserved in
`results/pareto_front.csv`; held-out values are reported for those frozen archive
members without using them to select the primary candidate.

## Limitations and next experiment

This proof uses a deterministic single-photon transfer-matrix loss model. It omits
partial distinguishability, multiphoton interference, detector response, source
impurity, fabrication tolerances and hardware calibration. The finite candidate pool
is deliberately centred on one calibration target, so performance need not transfer
to unrelated topologies or target states. Twelve paired episodes provide uncertainty
estimation but remain a small sample.

The next defensible experiment is to keep the gate fixed, preregister several target
families, add Perceval source/detector noise and partial distinguishability, and reserve
an entirely different topology family as the held-out environment. Hardware claims
must wait for an independently calibrated photonic device.

## Reproduction and integrity

`./reproduce.sh` recreates the environment from `uv.lock`, runs unit tests, regenerates
all traces/tables/figures, and checks fairness invariants. `checksums.sha256` binds the
delivered artifacts. No external dataset, commercial API, closed-source model or QPU
was used. Code is released under MIT; generated-data terms are in
`DATA_LICENSE.md`.

## Sources

- Perceval 1.2 documentation: https://perceval.quandela.net/docs/v1.2/
- Official source repository and licence: https://github.com/Quandela/Perceval
- Exact simulator release: https://pypi.org/project/perceval-quandela/1.2.4/
"""
    (output_root / "REPORT.md").write_text(report, encoding="utf-8")

    negative_findings = []
    for baseline in ("random", "greedy"):
        fidelity = comparison_lookup(
            comparison_rows, baseline, "heldout_fidelity_q25"
        )
        success = comparison_lookup(
            comparison_rows, baseline, "heldout_success_q25"
        )
        negative_findings.append(
            "- Against {baseline}, BADS changed held-out fidelity q25 by {fd:.4f} "
            "(95% paired bootstrap CI {fl:.4f} to {fh:.4f}) and survival q25 by "
            "{sd:.4f} (CI {sl:.4f} to {sh:.4f}).".format(
                baseline=POLICY_LABELS[baseline],
                fd=float(fidelity["mean_paired_difference"]),
                fl=float(fidelity["paired_ci95_low"]),
                fh=float(fidelity["paired_ci95_high"]),
                sd=float(success["mean_paired_difference"]),
                sl=float(success["paired_ci95_low"]),
                sh=float(success["paired_ci95_high"]),
            )
        )
    gap_lines = []
    for policy in config["policies"]:
        gap = aggregate_lookup(
            aggregate_rows, policy, "fidelity_generalization_gap"
        )
        gap_lines.append(
            f"- {POLICY_LABELS[policy]}: mean training-minus-held-out fidelity q25 "
            f"gap {float(gap['mean']):.4f} (95% CI {float(gap['mean_ci95_low']):.4f} "
            f"to {float(gap['mean_ci95_high']):.4f})."
        )
    negative_report = f"""# Negative results and failure interpretation

## Preregistered status

The discovery gate **{status}**. This status is determined from the frozen rule in
`config/experiment.json`; no metric, seed, baseline or threshold was changed after the
run.

## Direct comparisons

{chr(10).join(negative_findings)}

## Distribution-shift gaps

{chr(10).join(gap_lines)}

## What is not established

- The run does not establish a new quantum-optical circuit or a global optimum.
- It does not show robustness to multiphoton, source, detector or fabrication noise.
- It does not show transfer beyond the finite candidate corpus and one target family.
- A higher scalar utility cannot be interpreted as simultaneous improvement in both
  fidelity and survival; the separate metrics and Pareto front must be read.
- Confidence intervals across 12 paired episodes may still be wide enough to include
  practically different effects.

## Diagnostic value

If the gate did not pass, the appropriate interpretation is that the present BADS
acquisition rule is not yet justified over simpler policies for this benchmark. A
useful follow-up is a preregistered ablation separating uncertainty and diversity,
followed by a topology-family shift. If the gate passed, the same limitations remain:
the result is evidence about search efficiency in this simulator only, not physical
discovery.

All failed and successful queries remain in `raw/query_log.jsonl`; none were removed
from the analysis.
"""
    (output_root / "NEGATIVE_RESULTS.md").write_text(
        negative_report, encoding="utf-8"
    )


def write_environment(output_root: Path, config_path: Path) -> None:
    import matplotlib as mpl

    text = "\n".join(
        [
            "QuantumOpt-Explorer frozen environment",
            f"python={platform.python_version()}",
            f"python_implementation={platform.python_implementation()}",
            f"platform={platform.platform()}",
            f"perceval-quandela={pcvl.__version__}",
            f"numpy={np.__version__}",
            f"matplotlib={mpl.__version__}",
            "simulator=Perceval ideal layer unitaries plus disclosed NumPy diagonal loss matrices",
            f"config_sha256={hashlib.sha256(config_path.read_bytes()).hexdigest()}",
            f"runner_sha256={hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}",
            "external_data=none",
            "commercial_api=none",
            "closed_source_model=none",
            "hardware_qpu=none",
            "",
        ]
    )
    (output_root / "environment.txt").write_text(text, encoding="utf-8")


def write_checksums(output_root: Path) -> None:
    excluded_parts = {".venv", "__pycache__"}
    files: list[Path] = []
    for path in output_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in excluded_parts for part in path.parts):
            continue
        if path.name == "checksums.sha256" or path.suffix == ".pyc":
            continue
        files.append(path)
    lines = []
    for path in sorted(files, key=lambda item: str(item.relative_to(output_root))):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(output_root)}")
    (output_root / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist_outputs(
    data: dict[str, list[dict[str, Any]]],
    output_root: Path,
    config: dict[str, Any],
    config_path: Path,
) -> None:
    write_jsonl(output_root / "raw" / "candidate_pool.jsonl", data["candidate_pool"])
    write_csv(output_root / "raw" / "loss_schedules.csv", data["loss_schedules"])
    write_jsonl(output_root / "raw" / "query_log.jsonl", data["query_log"])
    write_csv(
        output_root / "raw" / "query_pattern_metrics.csv",
        data["query_pattern_metrics"],
    )
    write_csv(
        output_root / "raw" / "final_pattern_metrics.csv",
        data["final_pattern_metrics"],
    )
    write_csv(output_root / "results" / "episode_summary.csv", data["episode_summary"])
    write_csv(output_root / "results" / "learning_curves.csv", data["learning_curves"])
    write_csv(output_root / "results" / "pareto_front.csv", data["pareto_front"])
    aggregate_rows, comparison_rows, gate_pass = aggregate_results(
        data["episode_summary"], config
    )
    write_csv(output_root / "results" / "aggregate_metrics.csv", aggregate_rows)
    write_csv(
        output_root / "results" / "statistical_comparisons.csv", comparison_rows
    )
    gate_record = {
        "experiment_name": config["experiment_name"],
        "discovery_gate_passed": gate_pass,
        "practical_fidelity_margin": config["practical_fidelity_margin"],
        "success_noninferiority_margin": config["success_noninferiority_margin"],
        "comparisons": [
            row for row in comparison_rows if str(row.get("comparison", "")).startswith("bads_vs_")
        ],
    }
    (output_root / "results" / "discovery_gate.json").write_text(
        json.dumps(json_ready(gate_record), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    make_figures(data, output_root, config)
    generate_report(output_root, config, aggregate_rows, comparison_rows, gate_pass)
    write_environment(output_root, config_path)
    write_checksums(output_root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("."))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    data = run_experiment(config)
    persist_outputs(data, output_root, config, config_path)
    print(
        json.dumps(
            {
                "status": "completed",
                "episodes": len(config["episode_seeds"]),
                "policies": config["policies"],
                "query_budget": config["query_budget"],
                "query_records": len(data["query_log"]),
                "perceval_version": pcvl.__version__,
                "output_root": str(output_root),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
