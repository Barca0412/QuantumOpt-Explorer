# QuantumOpt-Explorer V2 frozen pilot protocol

Status: implementation protocol frozen before the full eight-seed run. This is
a simulation-only, fixed-topology calibration benchmark. It is not a claim of a
new optical gate, a new topology, hardware validation, or a general quantum
experiment-discovery system.

## Scientific question

Under a fixed oracle-query budget, can a disclosed search policy find angular
compensations for a noisy heralded photonic CNOT whose lower-quartile usable
success transfers to a stronger, asymmetric held-out noise mechanism?

The circuit is Perceval 1.2.4's six-mode catalog `heralded cnot`. Its topology
is unchanged. A candidate is an eight-dimensional vector of additive angular
compensations in radians, ordered as the six beam splitters encountered in the
flattened catalog circuit and then its two internal phase shifters. Candidate 0
is the exact zero-compensation catalog control.

## Inputs and metrics

Every oracle evaluation uses all four dual-rail computational inputs: `00`,
`01`, `10`, and `11`. The primary per-draw quantity is unconditional usable
success,

`P(correct logical output AND exactly one photon in each herald mode)`.

The frozen primary robustness metric is the 25th percentile (`q25`) of usable
success over noise draws. The 10th percentile is retained only as a secondary
diagnostic. We separately export mean herald probability, conditional
truth-table fidelity, false-herald probability, logical-subspace leakage, and
logical error. Truth-table fidelity is not called process fidelity.

An ideal zero-compensation sanity check must reproduce conditional truth-table
fidelity 1 and herald/usable success `2/27` for all four inputs.

## Noise and distribution shift

Only three mechanisms are in scope:

1. One static six-element beam-splitter angle offset is drawn per device seed
   and reused in train and held-out evaluations.
2. Two phase-shifter errors are drawn per evaluation. Held-out draws add common
   correlation, greater variance, and an asymmetric bias.
3. Six mode-specific losses are drawn per evaluation and implemented as native
   Perceval `LC` components. Held-out draws have greater mean/variance, common
   correlation, and asymmetric mode biases.

No source brightness, multiphoton contamination, partial distinguishability,
detector inefficiency/dark counts, time drift, or hardware data is modeled.

## Frozen design

The full pilot uses eight paired device seeds, 128 candidates per seed, 32
total train-oracle queries per search policy, four shared deterministic warmup
queries, eight train noise draws per candidate, and 16 held-out draws for the
frozen finalist. Random, nearest-neighbor greedy, and Budget-Aware Diversity
Search (BADS) have the same candidate corpus, warmup, query budget, and noise
schedule. The untuned catalog control evaluates candidate 0 once; it does not
receive a fictional 32-query calibration budget.

BADS is the disclosed local benchmark policy in this repository, not a claim
to implement a separately published optimizer. It uses kernel-weighted score
prediction plus a budget-decaying distance bonus. Random and policy RNGs are
local, seed-derived NumPy generators.

## Leakage barrier

`reset(seed)` materializes the candidate corpus, static device offset, and
train draws only. `query(index)` can access train draws only. `freeze(index)`
is irreversible, prohibits further queries, and only then materializes held-out
draws. `evaluate_heldout()` raises before freeze. `query_log.jsonl` contains
train query events only; held-out results live in a separate file. Unit tests
exercise this order, and `verify` rejects any `heldout` field in the query log.

The canonical SHA-256 configuration hash covers the entire parsed JSON
configuration. The distinct protocol hash covers that configuration plus the
fixed code-level protocol contract (task, candidate ordering, inputs, primary
metric, noise families, and leakage rule). Both hashes appear in every
score-bearing row and the run manifest.

## Predeclared signal and claim gate

For BADS versus both the untuned catalog and random baselines, the quantitative
pilot signal requires all of the following:

- higher held-out usable-success q25 in at least six of eight paired seeds;
- mean paired relative improvement of at least 10%; and
- mean conditional truth-table fidelity decline no worse than 0.01 absolute.

All comparisons are paired by device seed and labeled descriptive, not
confirmatory. With eight seeds, normal-approximation confidence intervals are
diagnostic only. After every policy has frozen its finalist, all 128 candidates
are evaluated on held-out draws as a context-only oracle. This oracle is never
available to a policy; it supplies post-search regret and is written separately.

The full configuration also runs Perceval process tomography on all 32 frozen
finalists at preregistered held-out draw 0. As an independent diagnostic, it
reports whether mean average gate fidelity is at least 0.90 for BADS and whether
the decline relative to catalog or random exceeds 0.01. This diagnostic is
explicitly not an Outcome A gate. The smoke configuration deliberately disables
this expensive check and labels its rows accordingly.

Outcome A requires exactly the three quantitative criteria above; tomography
does not add a fourth post-hoc condition.
Outcome B requires a same-direction train/held-out ranking reversal in at least
six of eight seeds; this is interpreted as a mechanism-shift crossover, not an
improvement. Outcome C is the reproducible null/negative case. Even outcome A
supports only a fixed-topology calibration claim; hardware and novel-gate
claims remain out of scope.

## Reproduction interface

```bash
python -m quantumopt_v2 run --config configs/v2_smoke.json --output runs/smoke
python -m quantumopt_v2 run --config configs/v2_pilot.json --output runs/v2
python -m quantumopt_v2 verify --run runs/v2 --golden evidence/golden_summary.json
```

`run` writes each owned artifact through a temporary file and atomic replace;
rerunning over an existing output directory leaves unrelated files untouched.
The query log records selection reason, remaining budget, evaluation count,
stop reason, and actual elapsed seconds. Because timing varies across machines,
the external golden comparison uses a normalized semantic query hash computed
after replacing only `elapsed_seconds` with null. The manifest still hashes the
raw query log, and `operational_log.jsonl` retains the timing-specific view.
The generated `golden_summary.json` is the schema-compatible candidate that an
independent release step may copy to the external `evidence` directory.
