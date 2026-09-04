from __future__ import annotations

import math
import unittest

import numpy as np

from quantumopt_v2.circuit import NoiseRealization, evaluate_cnot, process_tomography


class IdealCnotTests(unittest.TestCase):
    def test_zero_compensation_reproduces_catalog_cnot_truth_table(self) -> None:
        """Catches topology or logical-rail changes that break the catalog CNOT."""
        result = evaluate_cnot(
            compensation=np.zeros(8, dtype=float),
            noise=NoiseRealization.ideal(),
        )

        self.assertTrue(math.isclose(result.conditional_truth_fidelity, 1.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(result.mean_herald_probability, 2 / 27, abs_tol=1e-12))
        self.assertTrue(math.isclose(result.mean_usable_success, 2 / 27, abs_tol=1e-12))
        self.assertTrue(math.isclose(result.mean_false_herald_probability, 0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(result.mean_leakage_probability, 0.0, abs_tol=1e-12))

    def test_ideal_evaluation_covers_all_four_computational_inputs(self) -> None:
        """Catches accidentally evaluating only an easy subset of the truth table."""
        result = evaluate_cnot(
            compensation=np.zeros(8, dtype=float),
            noise=NoiseRealization.ideal(),
        )

        self.assertEqual([row.input_label for row in result.input_rows], ["00", "01", "10", "11"])
        self.assertEqual(
            [row.expected_output_label for row in result.input_rows],
            ["00", "01", "11", "10"],
        )
        self.assertTrue(
            all(
                math.isclose(row.conditional_truth_fidelity, 1.0, abs_tol=1e-12)
                for row in result.input_rows
            )
        )

    def test_ideal_process_tomography_matches_cnot(self) -> None:
        """Catches coherent phase errors that a computational truth table misses."""
        result = process_tomography(
            compensation=np.zeros(8, dtype=float),
            noise=NoiseRealization.ideal(),
        )

        self.assertTrue(math.isclose(result.average_gate_fidelity, 1.0, abs_tol=1e-10))
        self.assertTrue(math.isclose(result.gate_efficiency, 2 / 27, abs_tol=1e-10))
        self.assertEqual(result.chi_matrix.shape, (16, 16))
        self.assertLess(result.chi_hermiticity_residual, 1e-10)


if __name__ == "__main__":
    unittest.main()
