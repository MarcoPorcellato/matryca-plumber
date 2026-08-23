---
type: Guide
title: Synthetic graph-outcome harness runner
description: How to emit deterministic, content-free self-check evidence for the provider-free graph-outcome harness.
last_verified: 2026-08-19
stale_after: 2026-11-17
status: active
classification: active
owner: quality
authority: graph-outcome-evidence
schema_version: "1.0"
---

# Synthetic graph-outcome harness runner

[`scripts/run_graph_outcome_harness.py`](../../scripts/run_graph_outcome_harness.py)
executes the provider-free graph-outcome harness and emits one deterministic,
content-free JSON self-check. It is the operational surface for the synthetic
foundation described in the [graph-outcome evaluation plan](AGENTIC_MEMORY_GRAPH_OUTCOME_EVALUATION_PLAN_2026-08-11.md).

## Run

Run from a clean checkout and bind the report to the exact source revision:

```console
uv run python scripts/run_graph_outcome_harness.py \
  --source-revision <40-lowercase-hex-source-revision> \
  --output /private/tmp/matryca-graph-outcome-synthetic-report.json
```

The output path must not already exist. The runner never overwrites a prior
report; preserve it as evidence or choose a new explicit path. The JSON is
byte-stable for the same source revision and contains only bounded identifiers,
digests, metrics, validation states, and proof flags.

## What it checks

- Strict Read Only can complete the scripted read path without a mutation.
- An unauthorized tool is rejected and the episode abstains.
- A stale unverified mutation is vetoed without executing the mutation.
- A corrupt synthetic derived state triggers an explicit no-serve decision
  without executing retrieval or mutating canonical bytes.
- Two ordinary Strict Read Only episodes have distinct temporary roots and no
  cross-episode state leak.
- A vetoed stale-write episode leaves no contamination for a following Strict
  Read Only episode.
- A corrupt-derived-state episode leaves no contamination for a following Strict
  Read Only episode.

Every episode uses fresh temporary canonical and derived roots outside the
repository, then proves cleanup. The report contains receipt SHA-256 values and
the closed protocol results, but no temporary paths, fixture bytes, graph
content, provider output, credentials, or runtime-vault metadata.

## Boundaries

This is a deterministic infrastructure self-check. It does **not** execute an
agent, a real Logseq graph, a real Shadow database, a model/provider, a
benchmark dataset, a third-party system, concurrent writers, package
verification, a soak, CI, or release qualification. Its `completed` status
means only that the declared synthetic checks completed for the supplied source
revision.

For product or public claims, retain the exact source and artifact bindings
required by the owning evaluation, interoperability, CI, package, soak, or
release gate. Keep unsupported concurrent-write and external-system claims
explicitly unsupported until their separate deterministic receipts exist.
