from __future__ import annotations

import unittest

from quantumopt_v2.environment import CalibrationEnvironment
from quantumopt_v2.policies import run_policy

from test_environment import tiny_config


class PolicyTests(unittest.TestCase):
    def test_search_policies_share_warmup_and_respect_equal_budget(self) -> None:
        """Catches unfair warmups, duplicate queries, or unequal search budgets."""
        config = tiny_config()
        query_sequences: dict[str, list[int]] = {}
        for policy in ("random", "greedy", "bads"):
            env = CalibrationEnvironment(config)
            env.reset(7)
            result = run_policy(policy, env)
            sequence = [row.candidate_index for row in result.observations]
            query_sequences[policy] = sequence
            self.assertEqual(len(sequence), config["query_budget"])
            self.assertEqual(len(sequence), len(set(sequence)))
            self.assertEqual(sequence[: config["warmup_queries"]], list(env.warmup_indices))
            self.assertEqual(result.queries_used, config["query_budget"])

        self.assertEqual(query_sequences["random"][:1], query_sequences["greedy"][:1])
        self.assertEqual(query_sequences["greedy"][:1], query_sequences["bads"][:1])

    def test_catalog_is_an_explicit_zero_compensation_control(self) -> None:
        """Catches the untuned control quietly receiving calibration budget."""
        env = CalibrationEnvironment(tiny_config())
        env.reset(7)
        result = run_policy("catalog", env)

        self.assertEqual(result.selected_candidate_index, 0)
        self.assertEqual(result.queries_used, 1)
        self.assertEqual(result.observations[0].candidate_index, 0)
        query_event = next(event for event in env.events if event["event"] == "query")
        self.assertEqual(query_event["selection_reason"], "untuned_zero_compensation_control")
        self.assertEqual(query_event["stop_reason"], "catalog_control_complete")
        self.assertEqual(query_event["budget_remaining"], tiny_config()["query_budget"] - 1)
        self.assertIn("elapsed_seconds", query_event)
        self.assertGreaterEqual(query_event["elapsed_seconds"], 0.0)
        self.assertIn("evaluation_count", query_event)

    def test_policy_freezes_before_heldout_evaluation(self) -> None:
        """Catches policy code consulting held-out metrics during selection."""
        env = CalibrationEnvironment(tiny_config())
        env.reset(7)
        run_policy("bads", env)
        event_types = [event["event"] for event in env.events]

        self.assertEqual(event_types.count("heldout_evaluation"), 1)
        self.assertLess(event_types.index("freeze"), event_types.index("heldout_evaluation"))
        self.assertTrue(all(event.get("split") != "heldout" for event in env.events[: event_types.index("freeze")]))

    def test_random_policy_is_seed_deterministic(self) -> None:
        """Catches use of nondeterministic process-global random state."""
        sequences = []
        for _ in range(2):
            env = CalibrationEnvironment(tiny_config())
            env.reset(7)
            result = run_policy("random", env)
            sequences.append([row.candidate_index for row in result.observations])
        self.assertEqual(sequences[0], sequences[1])


if __name__ == "__main__":
    unittest.main()
