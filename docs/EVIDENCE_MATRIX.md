# Semifinal evidence matrix

**Audit date:** 2026-09-05
**Official target:** GOAI AI for Research, Open Exploration, current
**45/35/15/5** rubric. See `docs/OFFICIAL_REQUIREMENTS.md` for source precedence.

Status terms are strict: **verified** means inspected in the release tree or
checked by a command; **generated** means a saved artifact exists but its values
still require the verifier; **pending** means it may not be cited as evidence.

## Rubric-to-evidence mapping

| Rubric dimension | QuantumOpt V2 evidence | Status / release condition |
| --- | --- | --- |
| **Problem definition and environment design (45%)** | `README.md`; `V2_PROTOCOL.md`; `CLAIMS_AND_LIMITATIONS.md`; `SCIENTIFIC_SIGNIFICANCE.md`; frozen `configs/v2_pilot.json`; `src/quantumopt_v2/`; `tests/` | Scope is explicitly fixed-topology, eight-parameter, simulated heralded-CNOT calibration. Release only if the protocol, config hashes, one-way `reset -> query -> freeze -> evaluate_heldout` state machine, and tests agree. |
| **Exploration process and research signals (35%)** | `runs/v2/query_log.jsonl`; `runs/v2/freeze_log.jsonl`; `runs/v2/heldout_results.jsonl`; `runs/v2/noise_schedule.csv`; `runs/v2/candidate_pool.csv`; `runs/v2/summary.csv`; `runs/v2/comparisons.csv`; `runs/v2/statistical_comparisons.csv`; `runs/v2/process_tomography.csv`; `runs/v2/process_tomography.jsonl`; `runs/v2/discovery_gate.json`; figures; `SEMIFINAL_REPORT.md` | **Pending until the frozen full run and verifier pass.** Interpret only the predeclared gate: positive, counterexample, crossover, or stable null. Tomography is diagnostic and cannot change Outcome A. Do not substitute post-deadline/live results. |
| **Inspectability and sustainability (15%)** | Equal-budget random and nearest-greedy baselines; catalog/no-compensation reference; `runs/v2/run_manifest.json`; complete logs; `evidence/golden_summary.json`; `reproduce.sh`; `uv.lock`; CI; `docs/LITERATURE_LANDSCAPE.md`; V1 archive/audit | Release only if a clean environment can run tests, smoke, full reproduction, and golden comparison, and if every saved result is reachable from a manifest/config hash. |
| **Open-source contribution (5%)** | Public repository; MIT `LICENSE`; `DATA_LICENSE.md`; `THIRD_PARTY_NOTICES.md`; `OPEN_SOURCE_PLAN.md`; `CONTRIBUTING.md`; `CHANGELOG.md`; `CITATION.cff`; reusable package/API; tests and CI | Licence/disclosure files are present. Recheck that dependency versions match `pyproject.toml`, `uv.lock`, notices, and run manifest before tagging. |

## Three-piece set

| Mandatory item | Direct evidence | Pass condition |
| --- | --- | --- |
| Minimum runnable exploration environment | `src/quantumopt_v2/`, `pyproject.toml`, `uv.lock`, `configs/`, tests, `reproduce.sh` | Fresh clone completes `./reproduce.sh --smoke`; no undocumented credentials, API, private data, or manual patching. |
| At least one complete exploration log | `runs/v2/query_log.jsonl`, held-out results, noise schedule, run manifest | Full run contains every policy action/observation, all paired device seeds, freeze boundary, configuration/hash metadata, and final evaluation. Search log contains no held-out observations. |
| Reference/baseline design | Random, nearest-greedy, and catalog/no-compensation results in code, protocol, log, and summary | Same candidate pool, warm-up information, query budget, and paired noise/device seeds for search policies; references clearly distinguished from comparable policies. |
| README and reproduction instructions | `README.md`, `reproduce.sh`, `V2_PROTOCOL.md` | Commands, environment, dependency versions, seeds/config, expected outputs, runtime guidance, and interpretation are consistent. |

## Scientific claim-to-artifact map

| Claim or boundary | Required direct evidence | Allowed wording |
| --- | --- | --- |
| Ideal catalog topology implements the four computational-basis CNOT mappings with conditional truth-table fidelity 1 and herald success `2/27`. | `tests/test_ideal_cnot.py`, saved run metadata, Perceval catalog, and Uskov et al. (2009). | "Ideal sanity check reproduced in Perceval 1.2.4." Not a V2 discovery. |
| Search cannot inspect held-out metrics before selection is frozen. | State-machine tests plus a schema/content audit of `query_log.jsonl`. | "Enforced in software and verified in the saved log" only after both checks pass. |
| Policies receive equal information and query budgets. | Frozen config, fairness tests, query counts, shared warm-up IDs, paired noise schedule. | "Equal-budget paired comparison" only if all counts/IDs match. |
| Primary metric measures useful physical rate rather than conditional accuracy alone. | Code and protocol definition of `usable_success`; per-input decomposition into conditional truth fidelity, herald success, false herald, and leakage. | Per-evaluation `usable_success = P(correct logical output AND accepted herald)`; policy-level primary metric is its held-out 25th percentile within this simulator. |
| Frozen-finalist process tomography supplies a separate coherence diagnostic. | `process_tomography.csv/jsonl`, frozen config (`heldout_draw_index: 0`), freeze log, gate/report, and Perceval tomography reference. | "Simulated Perceval average gate fidelity and gate efficiency on predeclared draw 0." It is not hardware evidence and does not alter the predeclared A/B/C gate. |
| A policy is better under the frozen synthetic OOD shift. | `summary.csv`, paired `comparisons.csv`, seed-level held-out rows, predeclared `discovery_gate.json`, golden verification. | Use the exact effect, uncertainty, and gate outcome. No claim until generated and verified. |
| Model represents a laboratory or transfers to hardware. | No device data or hardware experiment exists. | **Not established.** Synthetic stress-test prior only. |
| V2 discovers a new CNOT or optical topology. | Catalog and literature show the topology and gate class pre-exist. | **Not claimed.** Fixed-topology robust-calibration pilot. |
| V1 established BADS superiority. | `archive/v1/reproducibility/results/discovery_gate.json` records `discovery_gate_passed: false`; `docs/V1_AUDIT.md` and `docs/V1_METRIC_SENSITIVITY.md` add verified post-hoc diagnostics. | **False.** V1 is preserved as a negative result and motivation; post-hoc analysis cannot relabel it. |

## Pre-release evidence gate

All boxes must be checked on the exact commit supplied to judges:

- [ ] `V2_PROTOCOL.md` and `configs/v2_pilot.json` are committed/tagged before
  the formal full run; the manifest records that frozen commit and both hashes.
- [ ] `uv sync --frozen --extra dev` succeeds from a fresh clone.
- [ ] `uv run --frozen pytest` passes, including ideal CNOT, information-leakage,
  equal-budget, determinism, schema, and golden-verifier tests.
- [ ] `./reproduce.sh --smoke` creates the documented smoke outputs.
- [ ] `./reproduce.sh --full` recreates the frozen results and reports a passing
  comparison with `evidence/golden_summary.json`.
- [ ] Full-run manifest records commit, config/protocol hashes, Python/platform,
  exact dependency versions, seeds, query budget, and output checksums.
- [ ] Logs contain no held-out metric before each policy's freeze event.
- [ ] Tomography has exactly one completed row for every frozen finalist in the
  full run, uses held-out draw 0, reports efficiency separately, and remains
  `diagnostic_not_outcome_gate`.
- [ ] Summary, report, figures, abstract, and defense slides state the same gate
  outcome and numerical values.
- [ ] `pyproject.toml`, `uv.lock`, `THIRD_PARTY_NOTICES.md`, and the run manifest
  agree on every direct dependency version.
- [ ] Public URLs resolve without login; code/data/report licences and third-party
  use are explicit.
- [ ] Submission ZIP excludes caches and transient runs but includes the complete
  V2 three-piece set and the judge-facing PDF.

The defense may clarify this evidence but cannot repair a missing log, failed
reproduction, absent licence, or unsupported result claim.
