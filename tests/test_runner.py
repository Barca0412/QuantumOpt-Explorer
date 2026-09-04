from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from quantumopt_v2.runner import _discovery_gate, run_experiment, verify_run

from test_environment import tiny_config


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_query_digest(path: Path) -> str:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["elapsed_seconds"] = None
    payload = "\n".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        for row in rows
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RunnerTests(unittest.TestCase):
    def test_run_writes_deterministic_auditable_artifacts(self) -> None:
        """Catches nondeterministic output and missing score-bearing evidence."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_experiment(tiny_config(), output)
            first_summary = digest(output / "summary.csv")
            first_queries = semantic_query_digest(output / "query_log.jsonl")
            run_experiment(tiny_config(), output)

            self.assertEqual(digest(output / "summary.csv"), first_summary)
            self.assertEqual(semantic_query_digest(output / "query_log.jsonl"), first_queries)
            expected = {
                "summary.csv",
                "comparisons.csv",
                "statistical_comparisons.csv",
                "query_log.jsonl",
                "heldout_results.jsonl",
                "freeze_log.jsonl",
                "noise_schedule.csv",
                "candidate_pool.csv",
                "postsearch_oracle.csv",
                "process_tomography.csv",
                "process_tomography.jsonl",
                "operational_log.jsonl",
                "learning_curves.csv",
                "discovery_gate.json",
                "run_manifest.json",
                "golden_summary.json",
                "learning_curves.png",
                "heldout_tradeoff.png",
            }
            self.assertTrue(expected.issubset({path.name for path in output.iterdir()}))

            with (output / "summary.csv").open(newline="", encoding="utf-8") as handle:
                summary = list(csv.DictReader(handle))
            self.assertEqual(len(summary), 4)
            self.assertTrue(all("heldout_usable_success_q25" in row for row in summary))
            self.assertTrue(all("heldout_regret_q25" in row for row in summary))
            gate = json.loads((output / "discovery_gate.json").read_text(encoding="utf-8"))
            self.assertIn(gate["outcome_class"], {"A", "B", "C"})
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertRegex(manifest["git_commit"], r"^[0-9a-f]{40}$")
            self.assertIsInstance(manifest["git_dirty"], bool)
            self.assertEqual(
                manifest["git_state_capture_point"],
                "before_output_directory_creation",
            )
            with (output / "comparisons.csv").open(newline="", encoding="utf-8") as handle:
                comparisons = list(csv.DictReader(handle))
            self.assertTrue(
                any(row["policy"] == "bads" and row["reference"] == "greedy" for row in comparisons)
            )

    def test_query_log_contains_no_heldout_data(self) -> None:
        """Catches held-out metrics or schedules leaking into policy observations."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_experiment(tiny_config(), output)
            rows = [
                json.loads(line)
                for line in (output / "query_log.jsonl").read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(len(rows), 1 + 3 * tiny_config()["query_budget"])
            self.assertTrue(all(row["event"] == "query" and row["split"] == "train" for row in rows))
            self.assertTrue(all("heldout" not in json.dumps(row).lower() for row in rows))
            required = {
                "selection_reason",
                "budget_remaining",
                "elapsed_seconds",
                "evaluation_count",
                "stop_reason",
            }
            self.assertTrue(all(required.issubset(row) for row in rows))
            self.assertTrue(all(isinstance(row["elapsed_seconds"], float) for row in rows))

    def test_outcome_a_depends_only_on_preregistered_quantitative_checks(self) -> None:
        """Catches process tomography being added post hoc as a fourth A gate."""
        config = tiny_config()
        config["gate"] = {
            "policy": "bads",
            "min_wins": 1,
            "min_relative_improvement": 0.10,
            "max_conditional_fidelity_decline": 0.01,
        }
        comparisons = [
            {
                "policy": "bads",
                "reference": reference,
                "wins": 1,
                "mean_relative_improvement": 0.11,
                "mean_difference_conditional_truth_fidelity": -0.005,
            }
            for reference in ("catalog", "random")
        ]
        summary = [
            {
                "seed": 7,
                "policy": policy,
                "train_usable_success_q25": 0.06,
                "heldout_usable_success_q25": 0.06,
            }
            for policy in config["policies"]
        ]
        gate = _discovery_gate(config, comparisons, summary, [])
        self.assertTrue(gate["quantitative_signal_pass"])
        self.assertEqual(gate["outcome_class"], "A")
        self.assertEqual(
            gate["coherent_process_tomography"]["role"],
            "diagnostic_not_outcome_gate",
        )

    def test_enabled_process_tomography_is_exported_for_each_finalist(self) -> None:
        """Catches a truth-table-only run being mislabeled as coherence-checked."""
        config = tiny_config()
        config["policies"] = ["catalog"]
        config["candidate_pool_size"] = 2
        config["query_budget"] = 1
        config["warmup_queries"] = 1
        config["train_draws"] = 1
        config["heldout_draws"] = 1
        config["process_tomography"] = {"enabled": True, "heldout_draw_index": 0}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_experiment(config, output)
            with (output / "process_tomography.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertGreater(float(rows[0]["average_gate_fidelity"]), 0.8)
            self.assertEqual(rows[0]["tomography_status"], "completed")

    def test_verify_accepts_golden_and_rejects_tampering(self) -> None:
        """Catches verification that trusts a manifest without hashing artifacts."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_experiment(tiny_config(), output)
            golden = output / "golden_summary.json"
            report = verify_run(output, golden)
            self.assertTrue(report["verified"])

            with (output / "summary.csv").open("a", encoding="utf-8") as handle:
                handle.write("tampered\n")
            with self.assertRaisesRegex(ValueError, "hash"):
                verify_run(output, golden)


if __name__ == "__main__":
    unittest.main()
