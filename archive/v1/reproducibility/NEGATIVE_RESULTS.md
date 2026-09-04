# Negative results and failure interpretation

## Preregistered status

The discovery gate **NOT PASSED**. This status is determined from the frozen rule in
`config/experiment.json`; no metric, seed, baseline or threshold was changed after the
run.

## Direct comparisons

- Against Random, BADS changed held-out fidelity q25 by -0.0602 (95% paired bootstrap CI -0.1659 to 0.0383) and survival q25 by -0.0024 (CI -0.0152 to 0.0081).
- Against Greedy, BADS changed held-out fidelity q25 by -0.0702 (95% paired bootstrap CI -0.1366 to -0.0159) and survival q25 by -0.0106 (CI -0.0262 to 0.0000).

## Distribution-shift gaps

- Random: mean training-minus-held-out fidelity q25 gap 0.0006 (95% CI 0.0002 to 0.0011).
- Greedy: mean training-minus-held-out fidelity q25 gap 0.0004 (95% CI 0.0002 to 0.0005).
- Budget-Aware Diversity Search: mean training-minus-held-out fidelity q25 gap 0.0008 (95% CI 0.0004 to 0.0014).

## What is not established

- The run does not establish a new quantum-optical circuit or a global optimum.
- It does not show robustness to multiphoton, source, detector or fabrication noise.
- It does not show transfer beyond the finite candidate corpus and one target family.
- A higher scalar utility cannot be interpreted as simultaneous improvement in both
  fidelity and survival; the separate metrics and Pareto front must be read.
- Confidence intervals across 12 paired episodes may still be wide enough to include
  practically different effects.

## Diagnostic value

If the gate did not pass, the appropriate interpretation is that the present BADS
acquisition rule is not yet justified over simpler policies for this benchmark. A
useful follow-up is a preregistered ablation separating uncertainty and diversity,
followed by a topology-family shift. If the gate passed, the same limitations remain:
the result is evidence about search efficiency in this simulator only, not physical
discovery.

All failed and successful queries remain in `raw/query_log.jsonl`; none were removed
from the analysis.
