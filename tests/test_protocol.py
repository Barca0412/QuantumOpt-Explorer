from __future__ import annotations

import unittest

from quantumopt_v2.protocol import config_hash, protocol_hash


class ProtocolHashTests(unittest.TestCase):
    def test_config_hash_is_independent_of_json_key_order(self) -> None:
        """Catches non-canonical hashes that differ for equivalent JSON."""
        left = {"query_budget": 3, "noise": {"sigma": 0.1, "mean": 0.2}}
        right = {"noise": {"mean": 0.2, "sigma": 0.1}, "query_budget": 3}
        self.assertEqual(config_hash(left), config_hash(right))

    def test_protocol_hash_changes_when_oracle_budget_changes(self) -> None:
        """Catches hashes that omit a score-bearing protocol field."""
        first = {"protocol_version": "2.0", "query_budget": 3}
        second = {"protocol_version": "2.0", "query_budget": 4}
        self.assertNotEqual(protocol_hash(first), protocol_hash(second))


if __name__ == "__main__":
    unittest.main()
