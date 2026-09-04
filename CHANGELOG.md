# Changelog

## 2.0.0 - 2026-09-05

- Reframed the research object from single-photon transfer-matrix approximation to
  fixed-topology heralded-CNOT calibration under device error.
- Added an explicit `reset -> query -> freeze -> evaluate_heldout` environment
  contract and tests that prevent held-out access during search.
- Added a decomposed unconditional success metric alongside conditional truth-table
  fidelity, herald probability, false herald, and leakage.
- Added catalog, random, nearest-greedy, finite-pool oracle, and Budget-Aware
  Diversity Search comparisons under paired candidates, budgets, and noise draws.
- Added protocol/config hashes, complete JSONL traces, a release golden fixture,
  public CI, licensing disclosure, and a judge-facing report.
- Preserved the preliminary package under `archive/v1/` and retained its negative
  discovery-gate result without revision.

## 1.0.0 - 2026-08-16

- Initial restricted four-mode single-photon calibration environment.
- Frozen 12-seed comparison of random, nearest-greedy, and BADS policies.
- The preregistered BADS discovery gate did not pass.
