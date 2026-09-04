# QuantumOpt-Explorer: Problem Definition

**Participant:** Haoming Chen  
**Team:** Haoming's team  
**Stream:** Open Exploration

## Research question

The environment is the research object: its hidden labels, query rules and discovery gate are fixed before an agent is evaluated. Can an agent discover compact linear-optical circuits that retain useful fidelity and success probability under unseen loss patterns while obeying a fixed component and simulation budget?

## Why an agent is appropriate

Circuit topology, continuous phases and non-ideal hardware interact in a rugged design space. An agent can choose what to simulate next, learn from failed candidates and explicitly trade depth, fidelity and robustness. A static predictor can rank candidates once; the proposed agent instead observes the result of each permitted action, updates a search belief and selects the next experiment. This makes policy quality, query allocation and stopping behaviour observable. The agent state contains the candidates already queried, their returned values, remaining budget and a versioned record of its selection rationale. The action space is deliberately constrained so the experiment is reproducible on a workstation.

## Exploration environment

The environment uses Perceval to construct circuits from a restricted catalogue of beamsplitters, phase shifters and modes. At reset, the agent receives a target transformation, component budget and training loss distribution. An action adds or edits a component. The oracle returns simulated success probability, fidelity, depth and constraint violations. Final candidates are evaluated against hidden loss distributions and random seeds. Episodes use deterministic seeds and publish the full reset configuration. The agent has no direct file access to hidden labels. A controller enforces budget, validates actions and records a complete JSONL trace containing observation hash, action, oracle reply, elapsed time and remaining resources. The environment exposes adapters for a random policy, a hand-coded policy and a learned policy through the same interface.

## Agent workflow

1. The **Environment Steward** loads the frozen split, budget and perturbation schedule.
2. The **Candidate Agent** proposes a valid next query and states which search objective it serves.
3. The **Oracle Adapter** executes the permitted simulation or hidden-label lookup.
4. The **Evidence Agent** updates the trajectory, uncertainty and diversity summaries.
5. The **Discovery Auditor** applies the preregistered gate only after the budget is exhausted or a stopping rule fires.

The separation prevents the same model from choosing the result definition after seeing an attractive trajectory. Researchers can pause, replay or substitute one policy without changing the environment.

## Discovery signal and minimum baseline

A discovery signal is a non-dominated circuit that improves worst-quartile fidelity or success probability over random and greedy search at equal simulation cost, while meeting the component budget. A robust discovery must retain its rank under held-out loss distributions rather than only the training perturbations. The minimum baseline samples valid topologies and phases uniformly. Greedy local search and the project-specific Budget-Aware Diversity Search provide more demanding comparisons. All methods receive identical candidate pools, budgets, random seeds and evaluation calls. Results are reported as distributions across episodes, not as the single best run. The primary comparison uses bootstrap confidence intervals; secondary views show query efficiency, diversity and failure concentration.

## What would count as a useful negative result

A negative result is valuable when the agent overfits the training loss model, when additional depth creates nominal gains but fragile behaviour, or when search overhead consumes the available simulation budget. The report retains failed trajectories and the exact decision that produced them. A null result therefore changes the next version of the problem: it may justify a stronger split, a different budget, a simpler policy class or a discovery gate that better captures robustness.

## Reproducibility, resources and current preparation

The Round 1 package now includes an executed Perceval 1.2.4 experiment, not a projected performance claim. Across 12 paired seeds, random, greedy and Budget-Aware Diversity Search each received the same 192-candidate pool, six warm-up queries, 48-query budget, 16 training loss patterns and 24 post-freeze held-out loss patterns. Mean held-out worst-quartile fidelity was 0.8574 for random, 0.8673 for greedy and 0.7971 for the diversity search. The preregistered discovery gate was not passed, so no search advantage is claimed. Code, the exact configuration and dependency lock, raw JSONL/CSV traces, aggregate tables, figures and a negative-result report are retained. One command reruns all policies and QA checks. The harness is released under MIT; generated-data terms and the boundary excluding future restricted hardware calibration files are explicit.

## Executed analysis and next experiment

The delivered analysis includes budget-normalised learning curves, paired seed comparisons, held-out distribution-shift gaps, frozen Pareto archives and query-level selection rationales. BADS won the fidelity comparison against random in only 6 of 12 episodes and in none of the 12 comparisons with greedy; its mean fidelity was lower than both baselines. All queries remain in the audit trail, so the result does not depend on removing unfavourable episodes. The next experiment will preregister separate uncertainty-only and diversity-only ablations, multiple target families and a topology-family holdout. That follow-up is deliberately identified as future work rather than counted as completed evidence.
