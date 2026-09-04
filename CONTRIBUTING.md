# Contributing

QuantumOpt-Explorer is intended to be extended without weakening its evidence
boundary.

1. Add new physics or device priors behind a versioned configuration field.
2. Add a deterministic test that distinguishes the new behavior from the current
   benchmark.
3. Keep held-out schedules inaccessible until `freeze`.
4. Give new policies the same candidates, warm-up observations, and query budget as
   existing search policies.
5. Preserve complete actions, observations, configuration hashes, and stopping
   reasons in the run log.
6. Declare any external data, API, model, hardware, cost, permission, and licence.
7. Predeclare a discovery or failure criterion before inspecting new held-out runs.

Bug fixes may update the patch version. Any change to the scientific question,
noise distribution, metric, policy budget, or outcome gate requires a new protocol
version and must not overwrite prior release evidence.
