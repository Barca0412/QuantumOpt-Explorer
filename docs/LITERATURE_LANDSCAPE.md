# Literature landscape and claim boundary

**Audit date:** 2026-09-05
**Defensible project label:** a protocol-frozen simulation pilot and auditable
benchmark for query-efficient, out-of-distribution robust calibration of a
**fixed** Perceval heralded-CNOT topology.

QuantumOpt-Explorer V2 does **not** claim a new quantum gate, a newly discovered
optical topology, hardware validation, or a general-purpose replacement for
MELVIN, Theseus, PyTheus, or Perceval. It searches eight additive compensation
angles (six beam-splitter and two phase parameters) while the six-mode catalog
topology remains fixed. Its intended contribution is the research environment:
a query budget, one-way search/held-out separation, decomposed physical metrics,
equal-budget baselines, complete traces, and release verification.

## Nearest discovery systems and calibration prior art

| Work | Primary contribution | Relationship to V2 | Tier / date / impact |
| --- | --- | --- | --- |
| [MELVIN: Automated Search for New Quantum Experiments](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.116.090405) | Automated discovery of experimental implementations for complex states and transformations, including unfamiliar asymmetric designs. | Establishes genuine experiment/topology discovery prior art. V2's fixed-topology parameter calibration must not be described as new-gate discovery. | Peer-reviewed primary paper; 2016-03-04; **challenges** novelty overclaim, **supports** automated optical exploration as a scientific field. |
| [Theseus](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.11.031044) and [official code](https://github.com/the-matter-lab/Theseus) | Interpretable graph representation plus fast inverse design and topological reduction for quantum-optical experiments. | Theseus searches experiment structure and extracts concepts; V2 freezes structure and studies calibration-policy behavior. | Peer-reviewed primary paper; 2021-08-26; **challenges** topology-discovery language, **supports** interpretable environment design. |
| [PyTheus paper](https://quantum-journal.org/papers/q-2023-12-12-1204/) and [official repository](https://github.com/artificial-scientist-lab/PyTheus) | Open-source graph discovery across states, measurements, communication protocols, heralded/post-selected gates, and continuous/discrete properties. It explicitly separates fidelity and count rate because fidelity alone can conceal a low event rate. | PyTheus is broader and already includes heralded-CNOT discovery examples. Its fidelity/count-rate warning directly motivates V2's unconditional `usable_success`, but precludes claiming that metric tension or gate search as novel. | Peer-reviewed primary paper and official code; 2023-12-12; **both supports and challenges**. |
| [Multipurpose self-configuration of programmable photonic circuits](https://www.nature.com/articles/s41467-020-19608-w) | Simulation and experimental self-configuration/optimization under nonuniform loss, parasitic errors, and crosstalk. | Establishes that automated photonic calibration is prior art. V2's narrower novelty, if any, is the auditable fixed-budget OOD benchmark contract, not calibration itself. | Peer-reviewed primary paper; 2020-12-11; **challenges** novelty overclaim, **supports** calibration relevance. |
| [Maximal success probabilities of linear-optical quantum gates](https://journals.aps.org/pra/abstract/10.1103/PhysRevA.79.042326) | Numerical evidence for maximum success probability `2/27` for a perfect-fidelity CNOT/controlled-sign gate with two unentangled ancilla resources. | Supports the ideal-reference sanity check; does not validate V2's noisy policy comparison. | Peer-reviewed primary paper; 2009-04-20; **supports** the ideal reference and **challenges** any claim that `2/27` was discovered here. |

## Perceval validation stack

| Official Perceval source | What it establishes | Project implication | Tier / date / impact |
| --- | --- | --- | --- |
| [Component catalog: `heralded cnot`](https://perceval.quandela.net/docs/v1.2/reference/components/catalog.html) | The public catalog already contains a Knill CNOT built from a heralded CZ and Hadamards, with two heralded modes. | This is the fixed circuit under study. V2 calibrates its components; it does not discover the gate. | Official v1.2 docs; accessed 2026-09-05; **both supports and challenges**. |
| [Processor, ports, and heralds](https://perceval.quandela.net/docs/v1.2/reference/runtime/processor.html) | A Processor applies source/component noise; output heralds filter states and affect reported performance. | Supports explicit herald and false-herald accounting rather than treating the conditional output distribution as the full physical result. | Official v1.2 docs; accessed 2026-09-05; **supports**. |
| [CNOT tomography walkthrough](https://perceval.quandela.net/docs/v1.2/notebooks/Tomography_walkthrough.html) | Perceval already supplies process tomography, process/average fidelity, physicality tests, and the catalog CNOT example. The walkthrough notes that normalized tomography can remove gate efficiency. | V2 calls its four-input score **conditional truth-table fidelity**, not process fidelity. The full run performs Perceval tomography only after all 32 finalists freeze, on predeclared held-out draw 0, and reports gate efficiency separately. It is an independent diagnostic, not a fourth Outcome-A gate or a novel method. | Official v1.2 docs; accessed 2026-09-05; **both supports and challenges**. |
| [NoiseModel](https://perceval.quandela.net/docs/v1.2/reference/utils/noise_model.html) | Supported parameters include brightness, indistinguishability, `g2`, transmittance, phase imprecision, and phase error; defaults are noiseless. | V2 models only disclosed static BS offsets, evaluation PS errors, and mode loss. It omits source impurity, distinguishability, multi-photon emission, detector effects, drift, and control constraints; therefore "hardware-realistic" is not claimed. | Official v1.2 docs; accessed 2026-09-05; **challenges** broad realism claims. |
| [Loss channel](https://perceval.quandela.net/docs/v1.1/reference/components/non_unitary_components.html) | `LC` is a non-unitary per-mode fixed-loss component implemented through a virtual loss mode. | Supports V2's mode-specific loss implementation, while remaining a simulation abstraction. | Official Perceval docs; accessed 2026-09-05; **supports** with a boundary. |
| [Perceval 1.2.4 release](https://github.com/Quandela/Perceval/releases/tag/v1.2.4) | Identifies the exact upstream release used by V2. | The version must remain frozen in `pyproject.toml` and `uv.lock`; Perceval remains third-party MIT-licensed software. | Official release; 2026-07-02; **supports** reproducibility. |

## What would falsify or narrow the V2 claim

- If equal-budget random or nearest-greedy matches/exceeds the proposed policy on
  the frozen held-out seeds, the predeclared result is a null/counterexample, not
  a discovery.
- If gains appear only in conditional truth-table fidelity while herald success
  falls, the primary `usable_success = P(correct logical output AND accepted
  herald)` does not support a useful improvement.
- If a policy can observe held-out fields before `freeze`, the central OOD claim
  is invalid regardless of aggregate scores.
- Even a positive synthetic result does not establish laboratory transfer. That
  requires measured device priors, source/detector imperfections, drift/control
  constraints, and independent experimental review.

The strongest honest positioning is therefore: **a small, inspectable fixed-
topology calibration benchmark that tests whether query allocation preserves
usable CNOT behavior under a disclosed synthetic distribution shift**.
