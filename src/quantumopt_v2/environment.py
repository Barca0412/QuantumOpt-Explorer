"""Leakage-resistant calibration environment for the V2 benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import time
from typing import Any, Iterable

import numpy as np

from .circuit import CnotEvaluation, NoiseRealization, evaluate_cnot
from .protocol import config_hash, protocol_hash


@dataclass(frozen=True)
class Observation:
    split: str
    candidate_index: int
    candidate_id: str
    query_number: int | None
    robust_score: float
    usable_success_q10: float
    usable_success_q25: float
    usable_success_mean: float
    conditional_truth_fidelity_q10: float
    conditional_truth_fidelity_mean: float
    herald_probability_mean: float
    false_herald_probability_mean: float
    leakage_probability_mean: float
    logical_error_probability_mean: float
    draws: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def candidate_id(vector: np.ndarray) -> str:
    payload = json.dumps(
        list(physical_candidate_key(vector)),
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def physical_candidate_key(vector: np.ndarray) -> tuple[float, ...]:
    """Canonicalize BS/PS compensations modulo their physical periods."""
    values = np.asarray(vector, dtype=float)
    if values.shape != (8,) or not np.all(np.isfinite(values)):
        raise ValueError("candidate must be a finite vector of length 8")
    periods = np.asarray([4 * np.pi] * 6 + [2 * np.pi] * 2, dtype=float)
    wrapped = np.mod(values, periods)
    wrapped[np.isclose(wrapped, periods, atol=1e-12, rtol=0.0)] = 0.0
    wrapped[np.isclose(wrapped, 0.0, atol=1e-12, rtol=0.0)] = 0.0
    return tuple(round(float(value), 12) for value in wrapped)


def assert_physical_candidate_uniqueness(candidates: np.ndarray) -> None:
    keys = [physical_candidate_key(vector) for vector in np.asarray(candidates, dtype=float)]
    if len(keys) != len(set(keys)):
        raise RuntimeError("candidate pool contains physically duplicate parameter settings")


def _required_positive_int(config: dict[str, Any], key: str) -> int:
    value = int(config[key])
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def validate_config(config: dict[str, Any]) -> None:
    pool_size = _required_positive_int(config, "candidate_pool_size")
    budget = _required_positive_int(config, "query_budget")
    warmup = _required_positive_int(config, "warmup_queries")
    _required_positive_int(config, "train_draws")
    _required_positive_int(config, "heldout_draws")
    if pool_size < budget:
        raise ValueError("candidate_pool_size must be at least query_budget")
    if warmup > budget:
        raise ValueError("warmup_queries cannot exceed query_budget")
    if len(config.get("seeds", [])) == 0:
        raise ValueError("seeds cannot be empty")
    policies = config.get("policies", [])
    if not policies or len(policies) != len(set(policies)):
        raise ValueError("policies must be a non-empty unique list")
    bounds = config["compensation_bounds"]
    if float(bounds["bs_radians"]) <= 0 or float(bounds["phase_radians"]) <= 0:
        raise ValueError("compensation bounds must be positive")
    if float(bounds["bs_radians"]) >= 2 * np.pi or float(bounds["phase_radians"]) >= np.pi:
        raise ValueError("compensation bounds span physically aliased parameter settings")
    for split in ("train", "heldout"):
        spec = config["noise"][split]
        if len(spec["phase_bias"]) != 2 or len(spec["mode_loss_bias"]) != 6:
            raise ValueError(f"{split} noise biases have invalid dimensions")
        lower, upper = (float(value) for value in spec["loss_clip"])
        if lower < 0 or upper >= 1 or lower >= upper:
            raise ValueError(f"{split} loss_clip must satisfy 0 <= lower < upper < 1")


def _bounds(config: dict[str, Any]) -> np.ndarray:
    values = config["compensation_bounds"]
    return np.asarray(
        [float(values["bs_radians"])] * 6 + [float(values["phase_radians"])] * 2,
        dtype=float,
    )


def _generate_candidates(seed: int, config: dict[str, Any]) -> np.ndarray:
    count = int(config["candidate_pool_size"])
    limits = _bounds(config)
    rng = np.random.default_rng(19_000_003 + int(seed))
    candidates = np.empty((count, 8), dtype=float)
    candidates[0] = 0.0
    if count > 1:
        candidates[1:] = rng.uniform(-limits, limits, size=(count - 1, 8))
    assert_physical_candidate_uniqueness(candidates)
    return candidates


def _maximin_warmup(candidates: np.ndarray, count: int, limits: np.ndarray) -> tuple[int, ...]:
    chosen = [0]
    normalized = candidates / limits
    while len(chosen) < count:
        distance = np.linalg.norm(
            normalized[:, None, :] - normalized[np.asarray(chosen)][None, :, :],
            axis=2,
        )
        min_distance = np.min(distance, axis=1)
        min_distance[np.asarray(chosen)] = -np.inf
        chosen.append(int(np.argmax(min_distance)))
    return tuple(chosen)


def _generate_static_bs_offset(seed: int, config: dict[str, Any]) -> np.ndarray:
    spec = config["noise"]
    rng = np.random.default_rng(23_000_033 + int(seed))
    values = rng.normal(0.0, float(spec["device_bs_sigma"]), size=6)
    clip = float(spec["device_bs_clip"])
    return np.clip(values, -clip, clip)


def _generate_noise_draws(
    seed: int,
    split: str,
    count: int,
    static_bs_offset: np.ndarray,
    config: dict[str, Any],
) -> tuple[NoiseRealization, ...]:
    if split not in {"train", "heldout"}:
        raise ValueError(f"unknown split: {split}")
    split_offset = 0 if split == "train" else 1_000_003
    rng = np.random.default_rng(29_000_059 + 10_007 * int(seed) + split_offset)
    spec = config["noise"][split]
    phase_bias = np.asarray(spec["phase_bias"], dtype=float)
    loss_bias = np.asarray(spec["mode_loss_bias"], dtype=float)
    lower, upper = (float(value) for value in spec["loss_clip"])
    rows: list[NoiseRealization] = []
    for _ in range(count):
        phase_common = rng.normal(0.0, float(spec["phase_common_sigma"]))
        phase = (
            phase_bias
            + phase_common
            + rng.normal(0.0, float(spec["phase_sigma"]), size=2)
        )
        loss_common = rng.normal(0.0, float(spec["loss_common_sigma"]))
        loss = (
            float(spec["loss_mean"])
            + loss_bias
            + loss_common
            + rng.normal(0.0, float(spec["loss_independent_sigma"]), size=6)
        )
        loss = np.clip(loss, lower, upper)
        rows.append(
            NoiseRealization(
                bs_offset=tuple(float(value) for value in static_bs_offset),
                phase_error=tuple(float(value) for value in phase),
                mode_loss=tuple(float(value) for value in loss),
            )
        )
    return tuple(rows)


def _aggregate(
    split: str,
    index: int,
    vector: np.ndarray,
    evaluations: Iterable[CnotEvaluation],
    query_number: int | None,
) -> Observation:
    rows = tuple(evaluations)
    usable = np.asarray([row.mean_usable_success for row in rows], dtype=float)
    fidelity = np.asarray([row.conditional_truth_fidelity for row in rows], dtype=float)

    def mean(field: str) -> float:
        return float(np.mean([getattr(row, field) for row in rows]))

    usable_q10 = float(np.quantile(usable, 0.10))
    usable_q25 = float(np.quantile(usable, 0.25))
    return Observation(
        split=split,
        candidate_index=index,
        candidate_id=candidate_id(vector),
        query_number=query_number,
        robust_score=usable_q25,
        usable_success_q10=usable_q10,
        usable_success_q25=usable_q25,
        usable_success_mean=float(np.mean(usable)),
        conditional_truth_fidelity_q10=float(np.quantile(fidelity, 0.10)),
        conditional_truth_fidelity_mean=float(np.mean(fidelity)),
        herald_probability_mean=mean("mean_herald_probability"),
        false_herald_probability_mean=mean("mean_false_herald_probability"),
        leakage_probability_mean=mean("mean_leakage_probability"),
        logical_error_probability_mean=mean("mean_logical_error_probability"),
        draws=len(rows),
    )


class CalibrationEnvironment:
    """Finite-corpus oracle with an irreversible freeze boundary."""

    def __init__(self, config: dict[str, Any]):
        validate_config(config)
        self.config = config
        self.config_hash = config_hash(config)
        self.protocol_hash = protocol_hash(config)
        self.events: list[dict[str, Any]] = []
        self.candidates = np.empty((0, 8), dtype=float)
        self.warmup_indices: tuple[int, ...] = ()
        self.seed: int | None = None
        self._train_noise: tuple[NoiseRealization, ...] = ()
        self._heldout_noise: tuple[NoiseRealization, ...] | None = None
        self._static_bs_offset = np.zeros(6, dtype=float)
        self._frozen_index: int | None = None
        self._query_count = 0
        self._cache: dict[tuple[str, int], Observation] = {}
        self.operational_events: list[dict[str, Any]] = []

    @property
    def is_frozen(self) -> bool:
        return self._frozen_index is not None

    @property
    def query_count(self) -> int:
        return self._query_count

    def reset(self, seed: int) -> dict[str, Any]:
        if int(seed) not in [int(value) for value in self.config["seeds"]]:
            raise ValueError(f"seed {seed} is not declared in the configuration")
        self.seed = int(seed)
        self.candidates = _generate_candidates(self.seed, self.config)
        self.warmup_indices = _maximin_warmup(
            self.candidates,
            int(self.config["warmup_queries"]),
            _bounds(self.config),
        )
        self._static_bs_offset = _generate_static_bs_offset(self.seed, self.config)
        self._train_noise = _generate_noise_draws(
            self.seed,
            "train",
            int(self.config["train_draws"]),
            self._static_bs_offset,
            self.config,
        )
        # Held-out draws are deliberately not materialized before freeze.
        self._heldout_noise = None
        self._frozen_index = None
        self._query_count = 0
        self._cache = {}
        self.events = []
        self.operational_events = []
        state = {
            "event": "reset",
            "seed": self.seed,
            "candidate_count": len(self.candidates),
            "dimension": 8,
            "warmup_indices": list(self.warmup_indices),
            "config_hash": self.config_hash,
            "protocol_hash": self.protocol_hash,
        }
        self.events.append(state.copy())
        return state

    def candidate(self, index: int) -> np.ndarray:
        if self.seed is None:
            raise RuntimeError("reset must be called before reading candidates")
        if index < 0 or index >= len(self.candidates):
            raise IndexError("candidate index out of range")
        result = self.candidates[index].copy()
        result.flags.writeable = False
        return result

    def _evaluate(self, index: int, split: str, query_number: int | None) -> Observation:
        key = (split, index)
        if key in self._cache:
            cached = self._cache[key]
            return Observation(**{**cached.to_dict(), "query_number": query_number})
        draws = self._train_noise if split == "train" else self._heldout_noise
        if draws is None:
            raise RuntimeError("heldout draws do not exist before freeze")
        vector = self.candidate(index)
        result = _aggregate(
            split,
            index,
            vector,
            (evaluate_cnot(vector, noise) for noise in draws),
            query_number,
        )
        self._cache[key] = result
        return result

    def query(
        self,
        index: int,
        *,
        selection_reason: str = "external_or_manual",
        stop_reason: str = "continue",
    ) -> Observation:
        if self.seed is None:
            raise RuntimeError("reset must be called before query")
        if self.is_frozen:
            raise RuntimeError("environment is frozen; further queries are forbidden")
        if self._query_count >= int(self.config["query_budget"]):
            raise RuntimeError("query budget exhausted")
        self._query_count += 1
        started = time.perf_counter()
        result = self._evaluate(index, "train", self._query_count)
        elapsed = time.perf_counter() - started
        event = {
            "event": "query",
            "seed": self.seed,
            **result.to_dict(),
            "candidate": [float(value) for value in self.candidate(index)],
            "selection_reason": selection_reason,
            "budget_remaining": int(self.config["query_budget"]) - self._query_count,
            "elapsed_seconds": float(elapsed),
            "evaluation_count": int(self.config["train_draws"]) * 4,
            "stop_reason": stop_reason,
            "config_hash": self.config_hash,
            "protocol_hash": self.protocol_hash,
        }
        self.events.append(event)
        self.operational_events.append(
            {
                "event": "query_timing",
                "seed": self.seed,
                "query_number": self._query_count,
                "candidate_index": index,
                "elapsed_seconds": elapsed,
                "evaluation_count": int(self.config["train_draws"]) * 4,
            }
        )
        return result

    def freeze(self, index: int) -> dict[str, Any]:
        if self.seed is None:
            raise RuntimeError("reset must be called before freeze")
        if self.is_frozen:
            raise RuntimeError("environment is already frozen")
        self.candidate(index)
        self._frozen_index = int(index)
        self._heldout_noise = _generate_noise_draws(
            self.seed,
            "heldout",
            int(self.config["heldout_draws"]),
            self._static_bs_offset,
            self.config,
        )
        event = {
            "event": "freeze",
            "seed": self.seed,
            "selected_candidate_index": self._frozen_index,
            "selected_candidate_id": candidate_id(self.candidates[self._frozen_index]),
            "queries_used": self._query_count,
            "config_hash": self.config_hash,
            "protocol_hash": self.protocol_hash,
        }
        self.events.append(event)
        return event

    def evaluate_heldout(self) -> Observation:
        if not self.is_frozen or self._frozen_index is None:
            raise RuntimeError("freeze must be called before heldout evaluation")
        result = self._evaluate(self._frozen_index, "heldout", None)
        self.events.append(
            {
                "event": "heldout_evaluation",
                "seed": self.seed,
                **result.to_dict(),
                "candidate": [float(value) for value in self.candidate(self._frozen_index)],
                "config_hash": self.config_hash,
                "protocol_hash": self.protocol_hash,
            }
        )
        return result

    def evaluate_heldout_context(self, index: int) -> Observation:
        """Post-freeze exhaustive oracle context; never counted as a train query."""
        if not self.is_frozen or self._heldout_noise is None:
            raise RuntimeError("freeze must be called before heldout oracle context")
        return self._evaluate(index, "heldout", None)

    def heldout_noise_draw(self, index: int = 0) -> NoiseRealization:
        if not self.is_frozen or self._heldout_noise is None:
            raise RuntimeError("freeze must be called before reading a heldout noise draw")
        if index < 0 or index >= len(self._heldout_noise):
            raise IndexError("heldout noise draw index out of range")
        return self._heldout_noise[index]

    def noise_schedule_rows(self) -> list[dict[str, Any]]:
        if not self.is_frozen or self._heldout_noise is None:
            raise RuntimeError("noise schedules are exportable only after freeze")
        rows: list[dict[str, Any]] = []
        for split, draws in (("train", self._train_noise), ("heldout", self._heldout_noise)):
            for draw_index, draw in enumerate(draws):
                row: dict[str, Any] = {
                    "seed": self.seed,
                    "split": split,
                    "draw_index": draw_index,
                    "mean_mode_loss": float(np.mean(draw.mode_loss)),
                }
                row.update({f"bs_offset_{i}": draw.bs_offset[i] for i in range(6)})
                row.update({f"phase_error_{i}": draw.phase_error[i] for i in range(2)})
                row.update({f"mode_loss_{i}": draw.mode_loss[i] for i in range(6)})
                rows.append(row)
        return rows
