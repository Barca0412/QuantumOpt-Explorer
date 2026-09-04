# GOAI AI for Research semifinal requirements

**Audit date:** 2026-09-05 (Asia/Singapore)
**Entry type:** Track 3, AI for Research, Open Exploration
**Authority rule:** the dated 2026-09-04 semifinal notice and the revised
2026-08-14 handbook control over the older 2026-08-10 recruitment article.

## Current scoring rubric

| Dimension | Weight | Evidence the judges say they seek |
| --- | ---: | --- |
| Problem definition and environment design quality | **45%** | A real, well-scoped scientific problem; a faithful environment; explicit fixed/explorable variables and feedback. |
| Exploration process and scientific/research signals | **35%** | A complete trace and an interpretable positive result, anomaly, counterexample, negative result, or useful problem revision. |
| Inspectability and sustainability | **15%** | Reference baselines, logs, reproduction instructions, and a credible continuation path. |
| Open-source contribution | **5%** | Reusable quality of the released code, environment, or data-processing pipeline. |

This **45/35/15/5** split is stated in both the revised handbook and the
2026-09-04 judging notice.[O1][O2] The 2026-08-10 recruitment article still
shows **45/30/20/5** and an obsolete Top-50/Top-15 timeline; it is retained as
counterevidence, not used for submission decisions.[O4]

## Mandatory semifinal package: the three-piece set

For an Open Exploration entry, the revised handbook requires:[O2]

1. **Minimum runnable exploration environment.** The evaluator must be able to
   install and run the environment, not merely inspect screenshots or prose.
2. **Exploration log from at least one complete run.** Preserve actions,
   observations, configuration, random seeds, and results sufficiently to audit
   the path to the conclusion.
3. **Reference/baseline design.** Include random exploration, a trivial solution,
   or another minimal reference system under a comparable protocol.

The package must also contain a README and clear reproduction instructions.[O2]
The live track page summarizes the semifinal deliverable as a runnable
environment/final code, technical documentation, and experiment/exploration
results.[O3]

## Repository, reproduction, and licence requirements

- From the semifinal onward, the handbook calls for runnable code or equivalent
  verifiable material and an **accessible repository**.[O2] It does not use the
  narrower phrase "a public GitHub repository is mandatory"; keeping this
  repository public is the conservative, inspection-friendly implementation.
- State the entry point, dependency installation, configuration method, random
  seeds, expected outputs, and end-to-end reproduction procedure.[O1][O2]
- Disclose every research-data source and its authorization/licence status.[O2]
- Disclose open-source dependencies, commercial services, external data,
  licences, and key versions. If commercial APIs or closed models are used,
  disclose call sites, cost assumptions, permission scope, alternatives, and
  reproducibility impact.[O2]
- Existing work is allowed, but the source, entrant's own contribution,
  innovation, and licence compatibility must be clear.[O2]

For QuantumOpt-Explorer these requirements are implemented through `LICENSE`,
`DATA_LICENSE.md`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff`, `pyproject.toml`,
`uv.lock`, `reproduce.sh`, the frozen configs, tests, and saved run artifacts.
The release gate in `docs/EVIDENCE_MATRIX.md` must be checked against the final
commit; a filename in this document is not evidence that the artifact exists.

## Timeline and online defense

The live track page gives the standard schedule as semifinal work from
2026-08-25 to **2026-09-03**, judging from 2026-09-04 to 2026-09-10, and the
finalist announcement on 2026-09-10.[O3] The 2026-09-04 notice specifies AI for
Research online defenses on **2026-09-05--06**, followed by review/calibration
on 2026-09-07--09.[O1]

The public defense description establishes the following:[O1]

- project presentation followed by judge Q&A within an allocated slot;
- independent pre-review, questioning, and scoring;
- evidence clarification based on the submitted materials;
- new on-site features do **not** replace formal results submitted by the
  deadline;
- approximately three expert judges, one host/timekeeper, and one recorder per
  venue; network interruption, lateness, and absence are recorded.

No public official source located by 2026-09-05 states the exact number of
presentation minutes or Q&A minutes. The following are therefore **portal/email
facts to verify**, not assumptions: the team's exact slot and meeting link,
presentation/Q&A duration, filename and size limits, whether a live demo is
requested, and the scope/cut-off of any team-specific permission to supplement
materials. These cannot be inferred from the public handbook.

## Official sources and precedence

| ID | Source | Source date | Tier | Evidence use |
| --- | --- | --- | --- | --- |
| O1 | [Semifinal judging officially launches](https://www.goaihz.com/en/news/Global%20Open-source%20AI%20Challenge%20Semi-Final%20Judging%20Officially%20Launches) | 2026-09-04 | Official, current dated notice | **Supports** current weights, judging focus, defense flow, evidence freeze, and schedule. |
| O2 | [AI for Research participant handbook and revision table (ZIP)](https://oss.goaihz.com/prod/20260814/7ccd16f5-39c0-4c9a-941f-dc52c3ffd13a.zip) | 2026-08-14 revision | Official handbook | **Supports** the three-piece set, 45/35/15/5, repository/reproduction, and disclosure rules. |
| O3 | [AI for Research live track page](https://www.goaihz.com/tracks?track=ai4s) | accessed 2026-09-05 | Official, current live page | **Supports** deliverable summary and current Top-40-to-Top-20 timeline. |
| O4 | [AI for Research recruitment article](https://www.goaihz.com/en/news/AI%20for%20Research) | 2026-08-10 | Official but superseded | **Challenges** stale 45/30/20/5 and Top-50/Top-15 figures; do not use as the current rubric. |
