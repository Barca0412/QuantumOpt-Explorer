from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT / "src"))

import quantumopt_experiment as experiment


class QuantumOptExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            (EXPERIMENT_ROOT / "config" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )

    def test_target_is_unitary(self) -> None:
        teacher = experiment.teacher_candidate(self.config["max_depth"])
        matrices = experiment.candidate_layer_matrices(
            teacher, self.config["modes"], {}
        )
        target = experiment.compose_transfer(matrices, self.config["modes"])
        identity = target.conj().T @ target
        np.testing.assert_allclose(
            identity, np.eye(self.config["modes"]), atol=1e-10, rtol=1e-10
        )
        self.assertAlmostEqual(
            experiment.normalized_process_fidelity(target, target), 1.0, places=12
        )

    def test_pool_is_unique_and_excludes_teacher(self) -> None:
        pool, _ = experiment.generate_candidate_pool(17, self.config)
        identifiers = [experiment.candidate_id(candidate) for candidate in pool]
        self.assertEqual(len(pool), self.config["candidate_pool_size"])
        self.assertEqual(len(identifiers), len(set(identifiers)))
        teacher_id = experiment.candidate_id(
            experiment.teacher_candidate(self.config["max_depth"])
        )
        self.assertNotIn(teacher_id, identifiers)
        self.assertTrue(
            all(
                experiment.component_count(candidate)
                <= self.config["max_components"]
                for candidate in pool
            )
        )

    def test_loss_schedules_are_reproducible_and_shifted(self) -> None:
        first = experiment.generate_loss_schedule(17, "train", self.config)
        repeat = experiment.generate_loss_schedule(17, "train", self.config)
        heldout = experiment.generate_loss_schedule(17, "heldout", self.config)
        np.testing.assert_array_equal(first, repeat)
        self.assertGreater(float(np.mean(heldout)), float(np.mean(first)))
        self.assertEqual(first.shape[0], self.config["train_loss_patterns"])
        self.assertEqual(heldout.shape[0], self.config["heldout_loss_patterns"])

    def test_evaluation_is_bounded_and_deterministic(self) -> None:
        pool, _ = experiment.generate_candidate_pool(17, self.config)
        teacher = experiment.teacher_candidate(self.config["max_depth"])
        target = experiment.compose_transfer(
            experiment.candidate_layer_matrices(teacher, self.config["modes"], {}),
            self.config["modes"],
        )
        schedule = experiment.generate_loss_schedule(17, "train", self.config)
        first, rows_first = experiment.evaluate_candidate(
            pool[0], target, schedule, self.config, {}
        )
        second, rows_second = experiment.evaluate_candidate(
            pool[0], target, schedule, self.config, {}
        )
        self.assertEqual(first, second)
        self.assertEqual(rows_first, rows_second)
        self.assertGreaterEqual(first["fidelity_q25"], 0.0)
        self.assertLessEqual(first["fidelity_q25"], 1.0)
        self.assertGreaterEqual(first["success_q25"], 0.0)
        self.assertLessEqual(first["success_q25"], 1.0)


if __name__ == "__main__":
    unittest.main()

