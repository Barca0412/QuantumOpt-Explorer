# Semifinal evidence matrix

**Audit date:** 2026-09-05
**Official target:** GOAI AI for Research, Open Exploration, current
**45/35/15/5** rubric. See `docs/OFFICIAL_REQUIREMENTS.md` for source precedence.

Status terms are strict: **verified** means inspected in the release tree or
checked by a command; **generated** means a saved artifact exists but its values
still require the verifier; **pending** means it may not be cited as evidence.
The scientific evidence below is verified locally. Publication checks remain
pending until the exact release commit, tag, URLs, and ZIPs exist remotely.

## Rubric-to-evidence mapping

| Rubric dimension | QuantumOpt V2 evidence | Status / release condition |
| --- | --- | --- |
| **Problem definition and environment design (45%)** | `README.md`; `V2_PROTOCOL.md`; `CLAIMS_AND_LIMITATIONS.md`; `SCIENTIFIC_SIGNIFICANCE.md`; frozen `configs/v2_pilot.json`; `src/quantumopt_v2/`; `tests/` | **Verified locally.** Scope is fixed-topology, eight-parameter, simulated heralded-CNOT calibration. The protocol/config hashes, one-way `reset -> query -> freeze -> evaluate_heldout` state machine, physical-candidate uniqueness checks, and 20 passing tests agree. |
| **Exploration process and research signals (35%)** | `runs/v2/query_log.jsonl`; `runs/v2/operational_log.jsonl`; `runs/v2/freeze_log.jsonl`; `runs/v2/heldout_results.jsonl`; `runs/v2/noise_schedule.csv`; `runs/v2/candidate_pool.csv`; `runs/v2/summary.csv`; `runs/v2/comparisons.csv`; `runs/v2/statistical_comparisons.csv`; `runs/v2/postsearch_oracle.csv`; `runs/v2/process_tomography.csv`; `runs/v2/process_tomography.jsonl`; `runs/v2/discovery_gate.json`; figures; `SEMIFINAL_REPORT.md` | **Verified locally: Outcome C.** BADS passed every preregistered check versus catalog but failed the win-count and 10% checks versus random. The exhaustive oracle and tomography remain post-search diagnostics and do not change Outcome A. |
| **Inspectability and sustainability (15%)** | Equal-budget random and nearest-greedy baselines; catalog/no-compensation reference; `runs/v2/run_manifest.json`; complete logs; `evidence/golden_summary.json`; `reproduce.sh`; `uv.lock`; CI; `analysis/verify_v2_semantics.py`; `docs/LITERATURE_LANDSCAPE.md`; V1 archive/audit | **Verified locally.** The built-in verifier checked 17 artifact hashes and 776 query rows; the independent verifier passed 11/11 semantic checks. The manifest records a clean source state. A final fresh-clone check remains required after publication. |
| **Open-source contribution (5%)** | Public repository; MIT `LICENSE`; `DATA_LICENSE.md`; `THIRD_PARTY_NOTICES.md`; `OPEN_SOURCE_PLAN.md`; `CONTRIBUTING.md`; `CHANGELOG.md`; `CITATION.cff`; reusable package/API; tests and CI | **Locally complete; publication pending.** Direct versions agree across `pyproject.toml`, `uv.lock`, notices, and the run manifest. Recheck the final public commit, release tag, and no-login URLs. |

## Verified full-run snapshot

Audited on 2026-09-05 against `runs/v2/`:

- protocol tag `v2-protocol-freeze` resolves to
  `479530929cbbc97bffe247c2ca0d60b60f4a8e13`;
- the release run records execution commit
  `8f8e17e9e8476f5e60654f9d0359ba2e63fb9132`, `git_dirty: false`,
  configuration hash `7cdec90c727e7065f69adf12fd28b4c667a66063d2ba540985d5bea941cc60ca`,
  and protocol hash
  `e1240e0f9ec37bb6425f3b0d23d575abe11558053c58e00dadc9f3e94dd82ac1`;
- the built-in verifier passed all 17 manifest artifacts and all 776 query
  rows; the independent semantic verifier passed 11/11 checks; 20 tests passed;
- candidate, oracle, noise, freeze/held-out, and tomography row counts are
  respectively 1,024, 1,024, 192, 32/32, and 32;
- BADS versus catalog: 8 wins, 0 ties, mean relative q25 improvement
  `+12.9069%`, mean absolute difference `+0.00699447`;
- BADS versus random: 4 wins, 4 ties, mean relative q25 improvement
  `+0.95645%`, mean absolute difference `+0.000565717`, descriptive 95%
  normal-approximation interval `[+0.000079878, +0.001051557]`; and
- all 32 tomography jobs completed. BADS mean average gate fidelity was
  `0.800664`, below the frozen `0.90` diagnostic threshold. This diagnostic
  remained separate from the A/B/C gate.

Therefore `discovery_gate.json` reports **Outcome C**, not BADS superiority.

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
| Exhaustive held-out finite-pool results contextualize finalist regret. | `postsearch_oracle.csv`, final selected candidate IDs, and protocol statement that this sweep occurs only after every policy freezes. | "Context-only post-search oracle." Never describe it as information available to a policy or as an equal-budget baseline. |
| BADS is better under the frozen synthetic OOD shift. | `summary.csv`, paired `comparisons.csv`, seed-level held-out rows, predeclared `discovery_gate.json`, golden verification. | **Not established.** Report Outcome C: the catalog comparison passed, but the random comparison failed the frozen win-count and 10% effect thresholds. |
| Model represents a laboratory or transfers to hardware. | No device data or hardware experiment exists. | **Not established.** Synthetic stress-test prior only. |
| V2 discovers a new CNOT or optical topology. | Catalog and literature show the topology and gate class pre-exist. | **Not claimed.** Fixed-topology robust-calibration pilot. |
| V1 established BADS superiority. | `archive/v1/reproducibility/results/discovery_gate.json` records `discovery_gate_passed: false`; `docs/V1_AUDIT.md` and `docs/V1_METRIC_SENSITIVITY.md` add verified post-hoc diagnostics. | **False.** V1 is preserved as a negative result and motivation; post-hoc analysis cannot relabel it. |

## Pre-release evidence gate

All boxes must be checked on the exact commit supplied to judges:

- [x] `V2_PROTOCOL.md` and `configs/v2_pilot.json` are committed/tagged before
  the formal full run; the manifest records the execution commit plus the
  frozen configuration and protocol hashes, and any later provenance-only fix
  is documented as non-scientific.
- [ ] `uv sync --frozen --extra dev` succeeds from the final public commit in a
  fresh clone.
- [x] `uv run --frozen pytest` passes, including ideal CNOT, information-leakage,
  equal-budget, determinism, schema, and golden-verifier tests.
- [ ] `./reproduce.sh --smoke` from the final public commit creates the
  documented smoke outputs.
- [ ] `./reproduce.sh --full` from the final public commit recreates the frozen
  results and reports a passing
  comparison with `evidence/golden_summary.json`.
- [x] Full-run manifest records commit, config/protocol hashes, Python/platform,
  exact dependency versions, seeds, query budget, and output checksums.
- [x] Logs contain no held-out metric before each policy's freeze event.
- [x] Tomography has exactly one completed row for every frozen finalist in the
  full run, uses held-out draw 0, reports efficiency separately, and remains
  `diagnostic_not_outcome_gate`.
- [x] Summary, report, figures, abstract, README, and judge-facing PDF state the
  same gate outcome and numerical values.
- [ ] Defense slides state the same gate outcome, values, and claim boundary.
- [x] `pyproject.toml`, `uv.lock`, `THIRD_PARTY_NOTICES.md`, and the run manifest
  agree on every direct dependency version.
- [ ] Public URLs resolve without login; code/data/report licences and third-party
  use are explicit.
- [ ] Submission ZIP excludes caches and transient runs but includes the complete
  V2 three-piece set and the judge-facing PDF.

The defense may clarify this evidence but cannot repair a missing log, failed
reproduction, absent licence, or unsupported result claim.
