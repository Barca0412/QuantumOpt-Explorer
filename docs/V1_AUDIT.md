# V1 frozen-evidence audit

**Audit status:** completed against the frozen V1 artifacts
**Evidence boundary:** repository files only; no hardware run or domain-expert review
**Claim vocabulary:** `VERIFIED`, `POST-HOC`, and `FUTURE WORK` are not interchangeable

## Executive finding

`VERIFIED` — V1 is a complete, internally consistent simulator run with a failed
discovery gate. It contains 12 paired episodes, three policies and 48 oracle
queries per policy/episode. The semantic verifier independently recomputes the
principal means and paired effects, checks the gate logic, validates query
fairness and loss-schedule shape, and compares the compressed submission evidence
with the expanded raw files.

`POST-HOC` — The most useful V1 scientific signal is not an agent advantage. It is
the diagnosis that the chosen normalized process-fidelity metric is nearly
insensitive to the stronger loss shift, while single-photon survival carries almost
all of the observed degradation. V1 also exposes a genotype/phenotype
canonicalization defect that caused four redundant physical queries by Greedy.

`FUTURE WORK` — V1 does not establish physical-device robustness, the cause of
BADS underperformance, or a new quantum-optical circuit. Those questions require
a new preregistered experiment rather than reinterpretation of V1.

## Frozen evidence inventory

| Artifact | Verified semantic content |
| --- | ---: |
| Candidate-pool records | 2,304 = 12 seeds × 192 genotypes |
| Query records | 1,728 = 12 seeds × 3 policies × 48 queries |
| Query-pattern records | 27,648 = 1,728 queries × 16 training patterns |
| Loss-schedule cells | 9,600 |
| Episode summaries | 36 |
| Final-pattern records | 12,600 |
| Learning-curve records | 1,728 |
| Pareto records | 315 |
| Discovery gate | `false` |

The frozen configuration is in
[`experiment.json`](../archive/v1/reproducibility/config/experiment.json). The
semantic expectations are stored separately in
[`v1_golden_summary.json`](../evidence/v1_golden_summary.json); unlike the V1
checksum QA, the verifier does not generate its own fixture before checking it.

Run:

```bash
python3 analysis/verify_v1_golden.py
python3 analysis/v1_metric_sensitivity.py
```

## Verified result: BADS did not pass the gate

| Comparison | Held-out fidelity mean difference | Paired 95% bootstrap CI | Wins / ties |
| --- | ---: | ---: | ---: |
| BADS − Random | −0.060206 | [−0.165854, 0.038316] | 6 / 1 |
| BADS − Greedy | −0.070157 | [−0.136562, −0.015895] | 0 / 6 |

The held-out fidelity means were Random `0.857352`, Greedy `0.867302`, and
BADS `0.797145`. Search AUC was also lower for BADS: its paired mean difference
was `−0.051825` versus Random and `−0.096406` versus Greedy. These values are
recomputed from
[`episode_summary.csv`](../archive/v1/reproducibility/results/episode_summary.csv)
and reconciled with
[`statistical_comparisons.csv`](../archive/v1/reproducibility/results/statistical_comparisons.csv).

This evidence supports only the statement that the frozen BADS rule did not
demonstrate an advantage in this benchmark. It does not isolate which BADS term
caused the failure because no preregistered uncertainty/diversity/annealing
ablation was run.

## Document-to-code discrepancies

| V1 narrative claim | Executed implementation | Audit disposition |
| --- | --- | --- |
| An action adds or edits a component. | Each action selects an index from a pre-generated 192-candidate pool. | Describe V1 as fixed-pool active search; do not claim online circuit editing. |
| The trace contains an observation hash, action, elapsed time and remaining resources. | The query row stores candidate ID/index, metrics, acquisition details and remaining budget; it has no observation hash or elapsed time. | Describe only the fields actually retained. |
| Random, hand-coded and learned policies share an adapter. | The executable branches directly among Random, Greedy and the hand-coded BADS rule. No learned policy is present. | Do not claim a learned-policy implementation. |
| A registered stopping rule may terminate an episode. | The loop always executes the complete 48-query budget. | Treat stopping as future interface work. |
| Five named agents form the workflow. | V1 is one deterministic Python runner; the named roles are conceptual separations, not deployed autonomous agents. | Present them as responsibilities, not implemented services. |

The narrative claims appear in
[`Problem_Definition_Source.md`](../archive/v1/source/Problem_Definition_Source.md#L15-L27).
The executed selection loop and query fields are in
[`quantumopt_experiment.py`](../archive/v1/reproducibility/src/quantumopt_experiment.py#L589-L650).

## Verified genotype/phenotype duplicate

The original uniqueness check hashes the complete genotype, including layers
beyond `candidate.depth`. A pattern-1 layer executes one beamsplitter and therefore
does not use its second theta gene, but that gene also remains in the genotype ID.
Consequently, distinct IDs can execute the same physical circuit.

The frozen pool contains four duplicate phenotype groups, one each in seeds 53,
97, 109 and 149. Each group contains two genotype IDs, so the episode-wise total is
2,300 unique executable phenotypes among 2,304 genotype rows. Greedy queried both
members in all four groups, consuming four of its nominally unique queries on already-evaluated
physical circuits. Random queried one member in two of those groups; BADS queried
neither duplicate pair twice.

The exact IDs and pool indices are in
[`v1_phenotype_duplicates.csv`](../evidence/v1_phenotype_duplicates.csv). The
mechanism is visible in candidate serialization at
[`quantumopt_experiment.py`](../archive/v1/reproducibility/src/quantumopt_experiment.py#L60-L76),
active-layer execution at
[`quantumopt_experiment.py`](../archive/v1/reproducibility/src/quantumopt_experiment.py#L204-L229),
and the ID-only uniqueness test at
[`test_quantumopt.py`](../archive/v1/reproducibility/tests/test_quantumopt.py#L40-L55).

This issue does not reverse the recorded BADS result and is not repaired inside
the frozen archive. Future candidate IDs and budget checks must use a canonical
executable phenotype.

## Scientific and technical boundary

`VERIFIED`:

- Perceval constructs the ideal four-mode layers; NumPy applies diagonal amplitude
  attenuation after each layer.
- The target is one disclosed five-layer teacher circuit, and each episode samples
  a finite mutation pool around it.
- Held-out patterns are evaluated only after the selected candidate and
  training-defined Pareto archive are frozen.
- The simulator, not a physical device, generated every result.

`POST-HOC`:

- Mean fidelity generalization gaps are only `0.000371–0.000840`, while survival
  gaps are `0.106403–0.112987`.
- Within selected candidates, held-out loss has mean Pearson correlation `−0.0283`
  with normalized fidelity and `−0.9999` with survival.
- This is consistent with the exact scale invariance of normalized process
  fidelity. It is a metric diagnostic, not evidence that loss has no physical
  effect. See [`V1_METRIC_SENSITIVITY.md`](V1_METRIC_SENSITIVITY.md).

`FUTURE WORK`:

- Make survival or a physically justified joint quantity co-primary.
- Add component-specific asymmetric loss, source and detector response, partial
  distinguishability, multiphoton interference and fabrication perturbations.
- Add multiple published target/topology families, stronger search baselines and
  preregistered BADS ablations.
- Canonicalize candidate phenotypes before pool deduplication and query accounting.
- Seek independent domain review or hardware validation; neither exists for V1.

## Evidence outputs

- [`v1_metric_sensitivity.json`](../evidence/v1_metric_sensitivity.json): complete
  machine-readable audit with source hashes and claim-status boundaries.
- [`v1_metric_sensitivity_by_policy.csv`](../evidence/v1_metric_sensitivity_by_policy.csv):
  train/held-out gaps and retained V1 confidence intervals.
- [`v1_metric_sensitivity_correlations.csv`](../evidence/v1_metric_sensitivity_correlations.csv):
  aggregate and within-candidate correlations.
- [`v1_uniform_loss_sweep.csv`](../evidence/v1_uniform_loss_sweep.csv): analytic
  scalar-attenuation sanity check.
- [`v1_metric_sensitivity.png`](../evidence/v1_metric_sensitivity.png): compact
  visual summary.
