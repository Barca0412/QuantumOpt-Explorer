# Scientific significance

Linear-optical gates are probabilistic and sensitive to component errors, so an
apparently high conditional fidelity can conceal a low rate of usable events. The
project turns that familiar engineering concern into a small, inspectable research
environment: an agent must allocate a fixed number of simulator queries, select a
calibration before stronger held-out errors are revealed, and preserve both logical
correctness and event probability.

The contribution is methodological rather than a new optical circuit. It provides:

1. a precise environment contract separating training observations from held-out
   device-error evaluation;
2. a decomposed physical score led by unconditional `usable_success` rather than a
   normalized fidelity alone;
3. equal-budget paired comparisons with full action-observation traces; and
4. an honest interpretation path for improvements, regime crossovers, and null
   results.

This framing is reusable for other heralded gates and calibration tasks. It also
exposes which additions are necessary before hardware relevance can be claimed:
measured error priors, source/detector imperfections, drift, control constraints,
and independent experimental review.
