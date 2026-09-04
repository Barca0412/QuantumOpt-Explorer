"""Deterministic, finite-budget policies for the frozen candidate corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .environment import CalibrationEnvironment, Observation


@dataclass(frozen=True)
class PolicyResult:
    policy: str
    observations: tuple[Observation, ...]
    selected_candidate_index: int
    selected_train_observation: Observation
    heldout_observation: Observation
    queries_used: int


def _best(observations: list[Observation]) -> Observation:
    # Stable tie break: score, then smaller candidate index.
    return max(observations, key=lambda row: (row.robust_score, -row.candidate_index))


def _normalized_candidates(env: CalibrationEnvironment) -> np.ndarray:
    bounds = env.config["compensation_bounds"]
    limits = np.asarray(
        [float(bounds["bs_radians"])] * 6 + [float(bounds["phase_radians"])] * 2,
        dtype=float,
    )
    return env.candidates / limits


def _available(env: CalibrationEnvironment, observed: list[Observation]) -> np.ndarray:
    used = {row.candidate_index for row in observed}
    return np.asarray([index for index in range(len(env.candidates)) if index not in used])


def _choose_random(
    env: CalibrationEnvironment,
    observed: list[Observation],
    rng: np.random.Generator,
) -> int:
    available = _available(env, observed)
    return int(rng.choice(available))


def _choose_greedy(
    env: CalibrationEnvironment,
    observed: list[Observation],
    _rng: np.random.Generator,
) -> int:
    features = _normalized_candidates(env)
    anchor = _best(observed).candidate_index
    available = _available(env, observed)
    distances = np.linalg.norm(features[available] - features[anchor], axis=1)
    return int(available[int(np.argmin(distances))])


def _zscore(values: np.ndarray) -> np.ndarray:
    spread = float(np.std(values))
    if spread <= 1e-15:
        return np.zeros_like(values)
    return (values - float(np.mean(values))) / spread


def _choose_bads(
    env: CalibrationEnvironment,
    observed: list[Observation],
    _rng: np.random.Generator,
) -> int:
    """Budget-Aware Diversity Search using a disclosed kernel-UCB rule."""
    features = _normalized_candidates(env)
    observed_indices = np.asarray([row.candidate_index for row in observed])
    observed_scores = np.asarray([row.robust_score for row in observed], dtype=float)
    available = _available(env, observed)
    distances = np.linalg.norm(
        features[available, None, :] - features[observed_indices][None, :, :],
        axis=2,
    ) / np.sqrt(features.shape[1])
    bandwidth = 0.55
    weights = np.exp(-0.5 * np.square(distances / bandwidth))
    predicted = (weights @ observed_scores) / np.maximum(np.sum(weights, axis=1), 1e-15)
    diversity = np.min(distances, axis=1)
    fraction_remaining = 1.0 - len(observed) / int(env.config["query_budget"])
    exploration_weight = 0.15 + 0.85 * fraction_remaining
    acquisition = _zscore(predicted) + exploration_weight * _zscore(diversity)
    return int(available[int(np.argmax(acquisition))])


_CHOOSERS: dict[
    str,
    Callable[[CalibrationEnvironment, list[Observation], np.random.Generator], int],
] = {
    "random": _choose_random,
    "greedy": _choose_greedy,
    "bads": _choose_bads,
}


def run_policy(policy: str, env: CalibrationEnvironment) -> PolicyResult:
    """Run one policy, freeze once, and only then request held-out metrics."""
    if env.seed is None:
        raise RuntimeError("environment must be reset before running a policy")
    if policy not in {"catalog", *_CHOOSERS}:
        raise ValueError(f"unknown policy: {policy}")

    observations: list[Observation] = []
    if policy == "catalog":
        observations.append(
            env.query(
                0,
                selection_reason="untuned_zero_compensation_control",
                stop_reason="catalog_control_complete",
            )
        )
        selected = observations[0]
    else:
        budget = int(env.config["query_budget"])
        for rank, index in enumerate(env.warmup_indices):
            observations.append(
                env.query(
                    index,
                    selection_reason=f"shared_maximin_warmup_{rank + 1}",
                    stop_reason="budget_exhausted" if len(observations) + 1 == budget else "continue",
                )
            )
        rng = np.random.default_rng(
            41_000_083 + 10_007 * int(env.seed) + {"random": 1, "greedy": 2, "bads": 3}[policy]
        )
        chooser = _CHOOSERS[policy]
        reasons = {
            "random": "seeded_uniform_unqueried",
            "greedy": "nearest_unqueried_to_best_observed",
            "bads": "kernel_prediction_plus_budget_decay_diversity",
        }
        while len(observations) < budget:
            index = chooser(env, observations, rng)
            observations.append(
                env.query(
                    index,
                    selection_reason=reasons[policy],
                    stop_reason="budget_exhausted"
                    if len(observations) + 1 == budget
                    else "continue",
                )
            )
        selected = _best(observations)

    env.freeze(selected.candidate_index)
    heldout = env.evaluate_heldout()
    return PolicyResult(
        policy=policy,
        observations=tuple(observations),
        selected_candidate_index=selected.candidate_index,
        selected_train_observation=selected,
        heldout_observation=heldout,
        queries_used=env.query_count,
    )
