# QuantumOpt-Explorer

An auditable open-exploration environment for query-efficient, out-of-distribution
robust calibration of a fixed-topology heralded photonic CNOT.

**Track:** GOAI Track 3, AI for Research - Open Exploration

**Participant:** Haoming Chen

**Semifinal release:** `semifinal-v2.0.0`

**Repository:** https://github.com/Barca0412/QuantumOpt-Explorer

## What this project claims

The scientific question is deliberately narrow: under a fixed query budget, can a
search policy select beam-splitter and phase compensations that retain useful CNOT
behavior under stronger, asymmetric held-out device errors? The environment treats
the Perceval catalog CNOT topology as fixed and exposes only six beam-splitter and
two phase compensation parameters.

This is a simulation pilot and reusable benchmark. It is not a hardware result, a
new-gate claim, or evidence of a globally novel optical topology. Positive,
counterexample, crossover, and stable negative outcomes were all defined before the
full run; the complete result is retained regardless of which outcome occurred.

## Frozen semifinal result

The preregistered result is **Outcome C: a reproducible negative pilot for BADS
superiority**. BADS beat the untuned catalog setting in 8/8 paired device seeds
with a mean relative held-out usable-success-q25 improvement of 12.91%. Against
equal-budget random search, however, it recorded only 4 wins and 4 ties with a
0.96% mean improvement, below the frozen 6/8-win and 10% thresholds. BADS and
nearest-greedy selected the same finalist in seven seeds.

All 32 post-freeze process-tomography jobs completed. BADS mean average gate
fidelity was 0.8007, below the disclosed 0.90 diagnostic threshold; tomography
did not alter the A/B/C gate. See `SEMIFINAL_REPORT.md` and
`runs/v2/discovery_gate.json` for the complete interpretation.

## Two-minute start

Requirements: Python 3.12-3.14, `uv`, and internet access for the first dependency
installation. On the release Apple-silicon host, the full simulator run took
approximately 5.25 minutes after environment setup; runtime varies by machine.

```bash
git clone https://github.com/Barca0412/QuantumOpt-Explorer.git
cd QuantumOpt-Explorer
./reproduce.sh --smoke
```

Run the frozen semifinal experiment and compare it with the release fixture:

```bash
./reproduce.sh --full
```

Equivalent explicit commands:

```bash
uv sync --frozen --extra dev
uv run --frozen pytest
uv run --frozen python -m quantumopt_v2 run \
  --config configs/v2_pilot.json --output runs/v2
uv run --frozen python -m quantumopt_v2 verify \
  --run runs/v2 --golden evidence/golden_summary.json
```

## Exploration contract

The public environment follows a one-way state machine:

```text
reset -> query -> freeze -> evaluate_heldout
```

During search, a policy can observe candidate parameters and training-noise metrics.
Held-out metrics are unavailable until the selected candidate is frozen. Random,
nearest-greedy, and Budget-Aware Diversity Search receive the same candidates,
warm-up observations, query budget, and noise schedules for each paired device seed.

The primary metric is `usable_success`, the unconditional probability that the
logical output is correct and the herald condition is accepted. Conditional truth-
table fidelity, herald success, false-herald probability, leakage, and post-search
tomography diagnostics are reported separately so that one metric cannot hide a
physical trade-off.

## Evidence map

| Artifact | Purpose |
| --- | --- |
| `V2_PROTOCOL.md` | Frozen question, environment, split, metrics, policies, and outcome gates |
| `runs/v2/query_log.jsonl` | Complete action-observation trajectory; no held-out fields |
| `runs/v2/noise_schedule.csv` | Exact train and held-out perturbations |
| `runs/v2/summary.csv` | Paired policy and catalog-reference outcomes |
| `runs/v2/comparisons.csv` | Effect sizes and seed-level comparisons |
| `runs/v2/discovery_gate.json` | Predeclared A/B/C interpretation |
| `SEMIFINAL_REPORT.md` and `output/pdf/` | Judge-facing research report |
| `docs/EVIDENCE_MATRIX.md` | Direct mapping to the 45/35/15/5 rubric |
| `evidence/golden_summary.json` | Independent release fixture used by `verify` |
| `archive/v1/` | Frozen preliminary package and expanded raw evidence |

## Reproducibility and licences

All candidate pools, device perturbations, and noise schedules are synthetic and
seeded. No proprietary dataset, commercial API, closed-source model, QPU, or
undisclosed calibration file is used. Source is MIT licensed; generated data is CC0;
reports and figures are CC BY 4.0. See `DATA_LICENSE.md` and
`THIRD_PARTY_NOTICES.md` for the complete disclosure.

Perceval 1.2.4 supplies the catalog topology and photonic simulation primitives.
The project-specific contribution is the frozen exploration protocol, query-budget
interface, OOD device-error split, equal-budget policy comparison, audit trail, and
release verification layer.

## Version boundary

`round1-v1.0.0` is the immutable preliminary submission. V1 used a restricted
four-mode single-photon transfer-matrix benchmark and retained a negative BADS
result. V2 changes the scientific object to a multiphoton heralded-CNOT calibration
pilot; it does not rewrite the V1 experiment or present post-hoc V1 diagnostics as
preregistered evidence.
