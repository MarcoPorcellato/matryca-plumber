---
type: evidence-index
title: Public quality evidence index
description: Bootstrap index of bounded, source-backed claims for Matryca Plumber.
resource: docs/quality/
tags: [quality, evidence, release, governance]
last_verified: 2026-08-19
stale_after: 2026-11-17
status: bootstrap
authority: evidence-index
---

# Public quality evidence index

This is a bootstrap index, not certification, an audit opinion, or an AAIF
submission. It records claims that can be traced to local, versioned source
documents. A `verified` row means that the cited source states and bounds the
claim; it does not extend the source's scope or replace a fresh qualification.

## Claim-record schema

Each record uses the following stable fields:

| Field | Meaning |
| --- | --- |
| Claim ID | Stable public identifier; do not reuse it for a different claim |
| Claim | Plain-language statement with an explicit boundary |
| Scope | Product, version, platform, artifact, or document scope |
| Authority | Maintained source that owns the claim |
| Source evidence | Exact local path, command, workflow, artifact, or digest when available |
| Status | `verified`, `partial`, `proposed`, `historical`, `external gate`, or `blocked` |
| Limitations | What the record does not establish |
| Review date | Date on which the row must be reviewed again |

Receipts must remain public-safe: no credentials, private filesystem paths, raw
user graph content, or unbounded logs.

## Seed records

| Claim ID | Claim | Scope | Authority | Source evidence | Status | Limitations | Review date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `V2-RELEASE-001` | Stable v2.0.0 is the external Shadow read-path release; Markdown remains authoritative and unhealthy Shadow falls back to Markdown-backed BM25 reads. | v2.0.0 stable | `docs/releases/v2.0.0-GITHUB.md`; `docs/knowledge/architecture/shadow-db.md` | Local release record names release commit `987446b8337f7abd308a9efe4abb834ce1acdc1b`; wheel SHA-256 `d3247aa1f4c2ea802c0bd94b180df61fef8d3f1faf62e0f3b920e483f74c4653`. | `verified` | Does not qualify future source changes, universal performance, or external review. | 2026-11-17 |
| `V2-SHADOW-CONTRACT-001` | Logseq Markdown is the source of truth; Shadow is disposable derived state, external to the graph under the current contract, and Strict Read Only blocks graph-local mutation while permitting validated cache maintenance. | Current v2 Shadow operator contract | `docs/knowledge/architecture/shadow-db.md` | Local contract table and health/fallback sections; implementation references `src/shadow/`. | `verified` | Does not prove concurrent-writer safety, a clean cache, or qualification on an unpinned checkout. | 2026-11-17 |
| `DOCS-VALIDATION-001` | The repository has blocking documentation checks for the knowledge bundle and generated inventory, plus agent-path/coherence checks. | Current repository checkout | `Makefile`; `.github/workflows/ci.yml` | `make docs-check` runs `scripts/docs_knowledge_check.py check-bundle`; `make agents-check` runs `scripts/check_agents_coherence.py`; CI invokes both. | `verified` | A passing local check is not proof that every public link, release, or remote workflow is current. | 2026-11-17 |
| `GATE-B-RC2-001` | The recorded RC2 Gate B campaign passed its two named profiles against the exact public RC2 artifact. | Historical v2.0.0 RC2 artifact | `docs/quality/GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`; `docs/quality/GATE_B_RC_SOAK_RUNBOOK.md` | Local terminal evidence and runbook identify exact-artifact binding, two profiles, checkpoint/recovery proof, and 417-cycle evidence. | `historical` | RC evidence does not transfer to stable or later source; each profile and artifact require independent requalification. | 2026-09-19 |
| `V2-STABLE-QUAL-001` | The local stable release record preserves the v2.0.0 readiness and publication evidence pointers, including cross-platform Shadow checks and artifact digests. | v2.0.0 stable publication record | `docs/releases/v2.0.0-GITHUB.md`; `docs/quality/issue-bodies/v2-rc-stable-readiness.md` | Local release record points to the readiness record, release workflow, GitHub release tag, and PyPI artifact. | `partial` | Publication and external service state are independent gates and must be freshly checked for a new release. | 2026-09-19 |

## Review rules

Refresh a row when its source commit, artifact, workflow contract, platform
matrix, or review date changes. Keep historical rows intact and add a new ID
when the claim's scope changes. `partial`, `blocked`, `external gate`, and
`historical` are not release PASS states. This index itself does not certify
AAIF readiness; any AAIF review or decision remains an external gate.
