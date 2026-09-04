# Claims, evidence, and limitations

## Evidence status

| Statement | Status | Direct evidence |
| --- | --- | --- |
| The environment enforces search/held-out separation. | Verified in software | State-machine tests and absence of held-out fields in `query_log.jsonl` |
| All compared policies receive equal query budgets and shared warm-up observations. | Verified in software | Configuration, query log, fairness tests |
| The ideal catalog CNOT maps all four computational inputs correctly. | Verified in simulation | Ideal-sanity test and run metadata |
| The ideal catalog heralding performance is 2/27. | Verified in Perceval 1.2.4 | Ideal-sanity test and Perceval catalog reference |
| The reported V2 policy comparison follows the frozen protocol. | Verified in saved run | Protocol/config hashes, noise schedule, raw log, summary, golden verifier |
| BADS cleared the preregistered advantage gate. | False; Outcome C | 8/8 wins and +12.91% versus catalog, but only 4 wins, 4 ties, and +0.96% versus random |
| Process tomography completed for all frozen finalists. | Verified in simulation | 32/32 rows in `process_tomography.csv`; diagnostic only, not an outcome gate |
| The simulated device-error distribution represents a particular laboratory. | Not claimed | Synthetic stress-test prior only |
| V2 discovers a new gate, circuit topology, or physical law. | Not claimed | Topology is fixed to the public Perceval catalog CNOT |
| Results transfer to hardware. | Not established | No device data or hardware experiment was used |

## Model boundary

V2 varies eight compensation parameters on a fixed topology. Its device model is
limited to static beam-splitter offsets, phase errors, and mode-specific linear loss.
It omits source impurity, partial photon distinguishability, detector dark counts,
time drift, thermal cross-talk, control quantisation, and calibration cost. The
training and held-out distributions are transparent synthetic priors, not measured
population distributions.

Truth-table behavior is evaluated on the four dual-rail computational inputs.
Conditional truth-table fidelity is not called process fidelity. A separate
tomography diagnostic is run only after policies freeze their final candidates.

## Interpretation guardrails

- A positive policy result supports only query-efficient robust calibration inside
  this synthetic benchmark.
- A crossover result is evidence that the best calibration can depend on the error
  regime; it is not evidence of a universal method ranking.
- A null result remains useful as a benchmark and problem-definition revision.
- The catalog reference and post-hoc finite-pool oracle are context, not additional
  search policies with comparable information access.
- No threshold, seed, primary metric, or held-out distribution may be changed after
  the full-run outputs are inspected.
- BADS finding the finite-pool held-out oracle candidate in 8/8 seeds is post-search
  context, not permission to bypass the frozen comparison against random.

## V1 boundary

The preliminary V1 result remains unchanged: its BADS heuristic did not pass the
predeclared discovery gate. V1's normalized transfer-matrix fidelity is weakly
sensitive to common attenuation by construction, while survival records that loss.
The accompanying V1 metric-sensitivity study is explicitly post-hoc and is used to
motivate V2's metric decomposition, not to relabel V1 as a positive discovery.

## Future work

The next study should use measured device priors or a disclosed hardware platform,
add source and detector imperfections, test topology families rather than one fixed
gate, and involve an independent quantum-optics reviewer. None of those extensions
is represented as completed work in this release.
