---
type: Runbook
title: Pocket Alpha 1A execution status
description: Maintained execution envelope for the bounded Pocket Alpha 1A contract work.
status: active
classification: active
audience: [maintainer, contributor]
owner: core-runtime
supersedes: []
related: []
---

# Pocket Alpha 1A execution status — 2026-08-24

| Field | Recorded value |
| --- | --- |
| Status | Alpha 1A execution envelope |
| Approved design | `7849017b91b830cb94271d606763697a0aebf336` |
| Implementation base | `af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e` |
| Upstream snapshot | `af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e` |
| Branch | `feat/pocket-alpha1a-contracts` |
| Pre-code documentation HEAD | `2794b831827eba0dc1a31823d4d4df26a5de03a1` |
| Allowed repositories | `matryca-plumber` only |
| Allowed production paths | `src/contracts/pocket`, `scripts/build_pocket_contract_bundle.py` |
| Allowed artifact paths | `contracts/pocket/v1`, `tests/contracts/pocket`, `docs/contracts/POCKET_V1.md` |
| Dependency policy | no `pyproject.toml` or `uv.lock` change |
| Locked validator evidence | `pydantic` `2.13.4`; `jsonschema` `4.26.0` |
| Knowledge projection | `degraded: sources.toml unresolved` — `matryca_status`: `[Errno 2] No such file or directory: 'sources.toml'` |
| Remote Git authority | none |
| Next gate | canonical JSON RED test |

## Isolation and baseline evidence

The implementation checkout is a clean linked worktree on the recorded branch,
sharing the repository common Git directory. At envelope capture it was two
commits ahead of `origin/main`: design transplant
`68060eaac8b70eff31363927ed22fc4d858d99f4` and plan transplant
`2794b831827eba0dc1a31823d4d4df26a5de03a1`. The dependency diff against
`origin/main...HEAD` for `pyproject.toml` and `uv.lock` was empty.

The canonical checkout remains unmodified by this task. Its observed status was
`main...origin/main [behind 14]` with modified `docs/knowledge/inventory.json`,
modified `docs/knowledge/inventory.md`, untracked `.worktrees/`, and untracked
`docs/quality/REPOSITORY_GOVERNANCE_AND_AAIF_READINESS_PROGRAMME_2026-08-19.md`.

## Leaf-module and graph-audit boundary

Bounded source inspection found no `src/contracts/pocket` path at the recorded
base. The inspected existing modules are `src/memory/benchmark_protocol.py`,
`src/memory/evidence_models.py`, and `scripts/run_interop_tck.py`; this task
does not modify their symbols or introduce a runtime import surface.

The user-authorized `rtk gitnexus analyze` exited 0 at the pre-code
documentation HEAD, with no embeddings flag and no cleanup. `rtk gitnexus
status` then reported the implementation repository indexed and current at
`2794b831827eba0dc1a31823d4d4df26a5de03a1` (the full pre-code documentation
HEAD). The fresh GitNexus query for `closed immutable contracts canonical JSON
bundle`, scoped to `matryca-plumber-alpha1a-impl`, returned existing canonical
contract surfaces including `canonical_event_bytes` in
`src/memory/evidence_models.py` and no `src/contracts/pocket` definition or
runtime flow. This fresh code-audit evidence permits the documentation-only
Task 1 checkpoint; it does not authorize production changes.

## Checkpoint identity

Intended subject: `docs(contracts): authorize Pocket Alpha 1A execution`.
This checkpoint cannot contain its own SHA. The next task must append the actual
Task 1 checkpoint SHA only after a fresh code-audit gate permits its commit.

## Approved stop conditions

Stop without an implementation commit if:

- the base differs from the approved execution envelope;
- a new dependency becomes necessary without separate admission;
- structural JSON Schema and Pydantic validation disagree on an invariant both
  layers are specified to enforce;
- canonical vectors differ across two runs;
- any real content, secret, key material, network access, or out-of-scope
  repository change appears;
- the full required verification cannot finish green.
