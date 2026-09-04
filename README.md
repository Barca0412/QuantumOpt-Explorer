# QuantumOpt-Explorer

**Preliminary-round attachment**  
**Track:** AI for Research — Open Exploration  
**Participant:** Haoming Chen  
**Team:** Haoming's team

## Start here

Open `QuantumOpt-Explorer_Problem_Definition.pdf`. This three-page problem-definition document is the primary submission material. It defines the research question, explains why an adaptive agent is appropriate, specifies the fixed and explorable parts of the Perceval environment, preregisters the discovery gate, establishes random and greedy baselines, and reports the completed preliminary experiment.

The current result is deliberately retained as a negative research signal. Under equal 48-query budgets across 12 paired seeds, Budget-Aware Diversity Search reached a mean held-out worst-quartile fidelity of 0.7971, compared with 0.8574 for random search and 0.8673 for greedy search. The preregistered discovery gate therefore did not pass. All episodes, including unfavourable runs, remain in the audit trail.

## Package map

| Path | Purpose |
| --- | --- |
| `QuantumOpt-Explorer_Problem_Definition.pdf` | Required problem-definition document; three pages |
| `source/Problem_Definition_Source.md` | Editable source narrative |
| `OPEN_SOURCE_PLAN.md` | Release scope, licensing and dependency disclosure |
| `reproducibility/README.md` | Experiment boundary and one-command reproduction guide |
| `reproducibility/config/experiment.json` | Frozen seeds, budgets, loss distributions and discovery gate |
| `reproducibility/src/` | Environment, policies, metrics, statistics and QA code |
| `reproducibility/tests/` | Deterministic unit and invariance tests |
| `evidence/query_log.jsonl.gz` | All 1,728 completed oracle-query records, gzip-compressed |
| `evidence/loss_schedules.csv.gz` | Exact training and held-out optical-loss draws, gzip-compressed |
| `evidence/README.md` | Evidence unpacking and compact-package note |
| `reproducibility/results/` | Episode summaries, paired comparisons, learning curves and Pareto archive |
| `reproducibility/REPORT.md` | Executed experimental report |
| `reproducibility/NEGATIVE_RESULTS.md` | Interpretation of the failed preregistered gate |
| `SHA256SUMS.txt` | Package-level integrity manifest |

## Reproduce the experiment

The experiment requires `uv`, Python 3.12–3.14 and internet access for the first dependency installation.

```bash
cd reproducibility
./reproduce.sh
```

The script installs the locked environment, runs the four unit tests, executes all paired policy episodes, regenerates raw traces, tables, figures and reports, and then checks the declared output invariants. The exact simulator version is Perceval 1.2.4.

To stay within the competition portal's 1000 KB attachment limit, the largest generated raw tables and PNG figures are not duplicated in the ZIP. The two most useful audit files are retained losslessly in `evidence/`; every omitted generated artifact is recreated by the command above from the frozen seeds and configuration.

## Evidence boundary

This package contains a deterministic simulator study of a restricted four-mode linear-optical circuit grammar. The model inserts disclosed mode-loss matrices after ideal Perceval layers. It does not include laboratory hardware, multiphoton interference, detector response, fabrication drift or undisclosed calibration data. Those omissions define the next experiment rather than being folded into the present result.
