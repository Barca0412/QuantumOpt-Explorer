# Preliminary experimental report

## Executive result

The frozen experiment completed 12 paired episodes for
three policies, with 48 training-oracle queries per policy and
episode. The preregistered discovery gate **NOT PASSED**. This is a bounded negative result: this version of the acquisition rule has not shown a reliable, practically sized held-out fidelity advantage over both simpler policies.

Values below are means with episode-resampled 95% bootstrap confidence intervals in
brackets. `objective loss` is one minus the disclosed scalar utility;
the fidelity and survival columns remain the scientific quantities of interest.

| Policy | Held-out fidelity q25 | Held-out survival q25 | Held-out objective loss | Search AUC |
| --- | ---: | ---: | ---: | ---: |
| Random | 0.8574 [0.7850, 0.9184] | 0.8278 [0.8210, 0.8388] | 0.1792 [0.1351, 0.2304] | 0.7580 [0.6940, 0.8173] |
| Greedy | 0.8673 [0.7678, 0.9552] | 0.8360 [0.8226, 0.8518] | 0.1686 [0.1099, 0.2387] | 0.8026 [0.7168, 0.8761] |
| Budget-Aware Diversity Search | 0.7971 [0.6827, 0.9011] | 0.8255 [0.8205, 0.8328] | 0.2254 [0.1481, 0.3113] | 0.7062 [0.6155, 0.7959] |

Paired policy differences use the same candidate pool, loss schedules, warm-up,
seeds, and query budget within every episode.

| Comparison | Fidelity difference | Survival difference | Fidelity wins |
| --- | ---: | ---: | ---: |
| BADS - Random | -0.0602 [-0.1659, 0.0383] | -0.0024 [-0.0152, 0.0081] | 6/12 |
| BADS - Greedy | -0.0702 [-0.1366, -0.0159] | -0.0106 [-0.0262, 0.0000] | 0/12 |

## Question and experiment boundary

The experiment asks whether an adaptive, budget-aware and diversity-seeking policy
can find compact linear-optical circuits that better retain a target transformation
under unseen loss than random or nearest-neighbour greedy search. It is a controlled
calibration benchmark. It does not claim that the fixed target, finite candidate pool,
or returned circuits are scientifically novel.

The target is the lossless transfer matrix of one disclosed five-layer, four-mode
Perceval circuit. Each episode contains 192 unique valid
candidates generated around that circuit; the exact pool is saved before search. The
three policies share the first 6 queries and then consume the
same total budget. Random follows a frozen permutation. Greedy queries the unobserved
design closest to its current best. BADS uses a k-nearest-neighbour prediction plus
annealed uncertainty and elite-distance terms; its exploration pressure falls as the
remaining budget shrinks.

## Optical simulation

Perceval 1.2.4 constructs every beam-splitter and phase-shifter layer and
computes its ideal unitary. After each layer, the harness applies the frozen diagonal
amplitude matrix `diag(sqrt(1 - intensity_loss))`. Training loss has mean
0.012 before clipping. Held-out loss is stronger,
asymmetric and shifted to mean 0.030 plus fixed
mode-specific biases. The exact per-mode, per-layer draws are in
`raw/loss_schedules.csv`.

Normalized process fidelity is the squared Hilbert-Schmidt overlap between the ideal
target and lossy transfer matrix, normalized by both matrix norms. Survival is the
mean single-photon transmission, `Tr(A^dagger A) / 4`. The policy observes the 25th
percentile over 16 training loss patterns. The selected circuit and the training-only
Pareto archive are frozen before evaluation on 24 held-out patterns.

## Discovery gate

The primary gate requires BADS to exceed both baselines by at least
0.010 mean held-out fidelity q25, with the lower
endpoint of each paired 95% bootstrap interval above zero. In addition, the lower
endpoint of the paired survival difference must be at least
-0.010. The result above follows that rule
without changing the threshold after inspection.

## What the traces show

`raw/query_log.jsonl` records every selection reason, observed training metric, budget
remainder and best-so-far utility. `raw/query_pattern_metrics.csv` retains the 16
pattern-level measurements behind every query. `results/learning_curves.csv` and
`figures/learning_curves.png` show query efficiency. The training-defined Pareto sets,
including fidelity, survival and component count, are preserved in
`results/pareto_front.csv`; held-out values are reported for those frozen archive
members without using them to select the primary candidate.

## Limitations and next experiment

This proof uses a deterministic single-photon transfer-matrix loss model. It omits
partial distinguishability, multiphoton interference, detector response, source
impurity, fabrication tolerances and hardware calibration. The finite candidate pool
is deliberately centred on one calibration target, so performance need not transfer
to unrelated topologies or target states. Twelve paired episodes provide uncertainty
estimation but remain a small sample.

The next defensible experiment is to keep the gate fixed, preregister several target
families, add Perceval source/detector noise and partial distinguishability, and reserve
an entirely different topology family as the held-out environment. Hardware claims
must wait for an independently calibrated photonic device.

## Reproduction and integrity

`./reproduce.sh` recreates the environment from `uv.lock`, runs unit tests, regenerates
all traces/tables/figures, and checks fairness invariants. `checksums.sha256` binds the
delivered artifacts. No external dataset, commercial API, closed-source model or QPU
was used. Code is released under MIT; generated-data terms are in
`DATA_LICENSE.md`.

## Sources

- Perceval 1.2 documentation: https://perceval.quandela.net/docs/v1.2/
- Official source repository and licence: https://github.com/Quandela/Perceval
- Exact simulator release: https://pypi.org/project/perceval-quandela/1.2.4/
