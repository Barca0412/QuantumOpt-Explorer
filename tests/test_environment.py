from __future__ import annotations

import unittest

import numpy as np

from quantumopt_v2.environment import (
    CalibrationEnvironment,
    assert_physical_candidate_uniqueness,
    physical_candidate_key,
)


def tiny_config() -> dict:
    return {
        "protocol_version": "2.0",
        "seeds": [7],
        "candidate_pool_size": 8,
        "query_budget": 3,
        "warmup_queries": 1,
        "policies": ["catalog", "random", "greedy", "bads"],
        "train_draws": 2,
        "heldout_draws": 3,
        "compensation_bounds": {"bs_radians": 0.12, "phase_radians": 0.20},
        "noise": {
            "device_bs_sigma": 0.025,
            "device_bs_clip": 0.06,
            "train": {
                "phase_sigma": 0.008,
                "phase_common_sigma": 0.0,
                "phase_bias": [0.0, 0.0],
                "loss_mean": 0.015,
                "loss_independent_sigma": 0.003,
                "loss_common_sigma": 0.002,
                "mode_loss_bias": [0.0] * 6,
                "loss_clip": [0.0, 0.05],
            },
            "heldout": {
                "phase_sigma": 0.02,
                "phase_common_sigma": 0.012,
                "phase_bias": [0.010, -0.008],
                "loss_mean": 0.045,
                "loss_independent_sigma": 0.006,
                "loss_common_sigma": 0.008,
                "mode_loss_bias": [0.0, 0.003, 0.006, 0.009, 0.012, 0.012],
                "loss_clip": [0.0, 0.12],
            },
        },
    }


class CalibrationEnvironmentTests(unittest.TestCase):
    def test_candidate_pool_is_unique_modulo_physical_periods(self) -> None:
        """Catches duplicate optical settings disguised by 4pi/2pi wrapping."""
        env = CalibrationEnvironment(tiny_config())
        env.reset(7)
        keys = [physical_candidate_key(candidate) for candidate in env.candidates]
        self.assertEqual(len(keys), len(set(keys)))

        aliases = np.zeros((2, 8), dtype=float)
        aliases[1, 0] = 4 * np.pi
        aliases[1, 6] = 2 * np.pi
        self.assertEqual(physical_candidate_key(aliases[0]), physical_candidate_key(aliases[1]))
        with self.assertRaisesRegex(RuntimeError, "physically duplicate"):
            assert_physical_candidate_uniqueness(aliases)

    def test_heldout_is_inaccessible_until_freeze(self) -> None:
        """Catches any API path that leaks held-out scores during search."""
        env = CalibrationEnvironment(tiny_config())
        state = env.reset(7)

        self.assertNotIn("heldout", state)
        with self.assertRaisesRegex(RuntimeError, "freeze"):
            env.evaluate_heldout()
        observation = env.query(0)
        self.assertEqual(observation.split, "train")
        self.assertEqual(observation.robust_score, observation.usable_success_q25)
        self.assertNotIn("heldout", observation.to_dict())

        env.freeze(0)
        with self.assertRaisesRegex(RuntimeError, "frozen"):
            env.query(1)
        heldout = env.evaluate_heldout()
        self.assertEqual(heldout.split, "heldout")
        event_types = [event["event"] for event in env.events]
        self.assertLess(event_types.index("freeze"), event_types.index("heldout_evaluation"))

    def test_postsearch_oracle_context_is_available_only_after_freeze(self) -> None:
        """Catches an exhaustive held-out oracle becoming a policy-side channel."""
        env = CalibrationEnvironment(tiny_config())
        env.reset(7)
        with self.assertRaisesRegex(RuntimeError, "freeze"):
            env.evaluate_heldout_context(1)
        env.query(0)
        env.freeze(0)
        before = env.query_count
        context = env.evaluate_heldout_context(1)
        self.assertEqual(context.split, "heldout")
        self.assertEqual(env.query_count, before)

    def test_reset_and_query_are_deterministic_for_a_seed(self) -> None:
        """Catches accidental dependence on process-global RNG state."""
        first = CalibrationEnvironment(tiny_config())
        second = CalibrationEnvironment(tiny_config())
        first.reset(7)
        second.reset(7)

        np.testing.assert_array_equal(first.candidates, second.candidates)
        self.assertEqual(first.warmup_indices, second.warmup_indices)
        self.assertEqual(first.query(0).to_dict(), second.query(0).to_dict())

    def test_query_budget_is_enforced(self) -> None:
        """Catches strategies silently exceeding the declared oracle budget."""
        env = CalibrationEnvironment(tiny_config())
        env.reset(7)
        env.query(0)
        env.query(1)
        env.query(2)
        with self.assertRaisesRegex(RuntimeError, "budget"):
            env.query(3)

    def test_heldout_schedule_is_a_stronger_asymmetric_shift(self) -> None:
        """Catches train and held-out schedules accidentally becoming identical."""
        env = CalibrationEnvironment(tiny_config())
        env.reset(7)
        env.query(0)
        env.freeze(0)
        env.evaluate_heldout()
        rows = env.noise_schedule_rows()
        train_loss = [row["mean_mode_loss"] for row in rows if row["split"] == "train"]
        heldout_loss = [row["mean_mode_loss"] for row in rows if row["split"] == "heldout"]

        self.assertGreater(float(np.mean(heldout_loss)), float(np.mean(train_loss)))
        static_offsets = {tuple(row[f"bs_offset_{i}"] for i in range(6)) for row in rows}
        self.assertEqual(len(static_offsets), 1)


if __name__ == "__main__":
    unittest.main()
