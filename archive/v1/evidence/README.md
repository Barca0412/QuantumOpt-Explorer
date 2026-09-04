# Compressed audit evidence

This directory retains the two largest audit records needed to inspect the completed experiment without rerunning it:

- `query_log.jsonl.gz` contains all 1,728 policy queries across 12 paired seeds and three policies. Each row records the selected candidate, search rationale, observed training-oracle metrics, best-so-far state and remaining budget.
- `loss_schedules.csv.gz` contains the exact training and held-out optical-loss draws used for every episode.

The files are ordinary gzip streams and can be inspected without modifying them:

```bash
gzip -cd evidence/query_log.jsonl.gz | head
gzip -cd evidence/loss_schedules.csv.gz | head
```

Candidate pools, per-pattern metric tables and PNG figures are deterministic generated artifacts. They are omitted only to meet the portal's 1000 KB attachment limit and are reconstructed by:

```bash
cd reproducibility
./reproduce.sh
```

The package-level `SHA256SUMS.txt` binds the compressed evidence exactly as delivered.
