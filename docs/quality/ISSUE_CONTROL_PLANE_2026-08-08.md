# Issue and milestone control plane — 2026-08-08

**Related execution dossier:** [Agentic Memory Leadership Programme — August 10, 2026](AGENTIC_MEMORY_LEADERSHIP_PROGRAMME_2026-08-10.md)

## Purpose and authority

This document is a timestamped execution ledger for EX-19 in the
[repository excellence study](REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md). It records
live GitHub evidence and proposes reversible metadata-only batches. It is not a release
authorization, does not replace issue bodies, and does not authorize closing issues or
changing Gate B evidence.

The repository and live GitHub state remain authoritative. Counts below are a snapshot,
not permanent repository facts.

## Snapshot provenance

- Repository: `MarcoPorcellato/matryca-plumber`
- Source branch: `ci/python313-evidence-401`
- Source commit: `4ad4174e263a962e6758bbd4872df2ea16b2abb4`
- Captured: `2026-08-08T00:45:52Z`
- Open issues: **65**
- Open issues without a milestone: **28**
- Open pull requests: **20**

The snapshot was captured read-only with `gh issue list`, `gh pr list`, and the GitHub
milestones API. Issue bodies were inspected for acceptance criteria, dependencies, and
closure evidence. Source paths named by the issues were checked at the source commit.
A local code-audit index was stale and was therefore used only for orientation, never as
closure or current-cycle proof.

### Revalidation commands

Before any proposed mutation phase, rerun these read-only queries from a clean checkout:

```bash
gh issue list --repo MarcoPorcellato/matryca-plumber --state open --limit 200 \
  --json number --jq 'length'
gh issue list --repo MarcoPorcellato/matryca-plumber --state open --limit 200 \
  --json number,milestone --jq '[.[] | select(.milestone == null)] | length'
gh issue list --repo MarcoPorcellato/matryca-plumber --state open --limit 200 \
  --json number,title,labels,milestone,updatedAt \
  --jq '.[] | select(.milestone == null) | [.number,.title,.updatedAt] | @tsv'
gh pr list --repo MarcoPorcellato/matryca-plumber --state open --limit 100 \
  --json number --jq 'length'
gh api --paginate \
  'repos/MarcoPorcellato/matryca-plumber/milestones?state=all&per_page=100' \
  --jq '.[] | [.number,.title,.state,.open_issues,.closed_issues] | @tsv'
```

If the totals, unmilestoned roster, issue `updatedAt`, milestone identifiers, or target
metadata differ, stop before mutation and refresh this ledger through review. Never widen
an allowlist to absorb drift during execution.

## Milestone inventory

| Milestone | State | Open | Closed | Disposition |
| --- | --- | ---: | ---: | --- |
| `v2.0.0 — Stable Shadow Read Path` | open | 13 | 28 | Preserve for stable-release blockers and explicitly accepted readiness work. |
| `v1.9.10 — Concurrency & Data Integrity` | open | 0 | 30 | Candidate to close after a read-only receipt check. |
| `v1.9.11 — Performance & I/O` | open | 4 | 16 | Migrate remaining work before closing the historical milestone. |
| `v1.9.12 — Code Perfection & Tech Debt` | open | 3 | 38 | Migrate remaining work before closing the historical milestone. |
| `v2.1.0 — Memory & Logseq DB Safe-Sync` | open | 17 | 2 | Preserve for the defined post-v2.0 product track. |
| `v1.9.9 — Security & Sandbox` | closed | 0 | 7 | Historical; no action. |
| `v1.9.6 - Agent UX` | closed | 0 | 2 | Historical; no action. |
| `v1.9.0 - Structural Graph Hygiene` | closed | 0 | 0 | Historical; no action. |
| `v1.8.0 - Edge Computing & Performance` | closed | 0 | 0 | Historical; no action. |

The open v1.9.x milestones should not absorb new work after the v2.0 release-candidate
line. The proposed successor is a new milestone, **`v2.1.x — Engineering Quality &
Security`**. Creating it, migrating issues, or closing historical milestones is a remote
mutation and requires separate maintainer authorization.

## Priority contract

The repository currently has no priority labels. The proposed metadata vocabulary is:

- `priority:P1`: release, security, or data-safety decision required before dependent work;
- `priority:P2`: high-value architectural work with material blast radius;
- `priority:P3`: bounded contributor-ready or routine quality work;
- `priority:P4`: exploratory or dependency-blocked work;
- `manual-review`: evidence is insufficient for an automatic disposition.

These labels are proposals only. No label was created or applied during this audit.

## Complete unmilestoned issue disposition

| Issue | Category | Priority | Recommended milestone | Dependency or relation | Closure evidence |
| ---: | --- | --- | --- | --- | --- |
| #334 | quality/tech-debt | P2 | new quality milestone | Daemon-core hotspot; coordinate with #205 and #212. | Upstream impact, behavior-preserving split, focused daemon tests, full CI, merged PR. |
| #333 | security | P1, manual-review | stable-blocker decision; otherwise new quality milestone | Bounded parser IPC protocol; both queue and raw-pipe paths. | Explicit protocol decision, adversarial serialization tests, performance receipt, full CI, merged PR. |
| #240 | quality/tech-debt | P2, manual-review | new quality milestone | Follow-up to #204; the old cycle inventory is not current proof. | Exact-current import-cycle report, focused fixes and tests, merged PR. |
| #236 | contributor-ready | P3 | new quality milestone | Standalone `inject_page_property` extraction. | Named focused tests, complexity check, full CI, merged PR. |
| #235 | contributor-ready | P3 | new quality milestone | Standalone property-list parser extraction. | Named focused tests, complexity check, full CI, merged PR. |
| #234 | contributor-ready | P3 | new quality milestone | Link-verification mutation helper. | Named focused tests, complexity check, full CI, merged PR. |
| #232 | contributor-ready | P3 | new quality milestone | Hierarchical summarization helper. | Named focused tests, complexity check, full CI, merged PR. |
| #231 | contributor-ready | P3 | new quality milestone | Generational-cache patch path. | Cache parity and concurrency tests, complexity check, full CI, merged PR. |
| #230 | contributor-ready | P3 | new quality milestone | Bootstrap catalog harvest path. | Harvest/OCC tests, complexity check, full CI, merged PR. |
| #229 | contributor-ready | P3 | new quality milestone | Pure balanced-bracket parser. | Parser edge-case tests, complexity check, full CI, merged PR. |
| #228 | contributor-ready | P3 | new quality milestone | Git-audit commit helper. | Git-audit tests, subprocess boundary checks, full CI, merged PR. |
| #227 | contributor-ready | P3 | new quality milestone | MARPA SSOT duplication scanner. | Lint-pipeline tests, complexity check, full CI, merged PR. |
| #226 | contributor-ready | P3 | new quality milestone | Backlink content updater. | Backlink parity tests, complexity check, full CI, merged PR. |
| #225 | contributor-ready | P3 | new quality milestone | Cognitive lint pipeline. | Pipeline-order and failure tests, complexity check, full CI, merged PR. |
| #223 | contributor-ready | P3 | new quality milestone | Tana journal date formatter. | Formatter/property tests, complexity check, full CI, merged PR. |
| #222 | contributor-ready | P3 | new quality milestone | Semantic index-section formatter. | Semantic-write tests, complexity check, full CI, merged PR. |
| #221 | contributor-ready | P3 | new quality milestone | Daemon LLM client indexing. | Client/indexing tests, complexity check, full CI, merged PR. |
| #220 | contributor-ready | P3 | new quality milestone | Agent-context loader. | Context-loading tests, complexity check, full CI, merged PR. |
| #219 | security/CI | P1 | new quality milestone | Canonical implementation candidate for audit finding #207. | Costed scheduled/CI design, first PDG baseline, reviewed findings, deterministic regression policy, merged PR. |
| #214 | quality/tech-debt | P2 | new quality milestone | Child of #205; `llm_client.py` remains 1,119 lines. | Phased module-boundary plan, API/import compatibility, focused tests, full CI, merged PR. |
| #213 | quality/tech-debt | P2 | new quality milestone | Child of #205; `ui_server.py` is now 1,299 lines. | Route/API contract checks, behavior-preserving slices, full CI, merged PRs. |
| #212 | quality/tech-debt | P2 | new quality milestone | Child of #205; `maintenance_daemon.py` is now 1,325 lines. | High-fan-out impact map, lifecycle tests, phased merged PRs. |
| #209 | quality epic | P2 | new quality milestone | Parent for the 2026 audit findings and TRIZ follow-ups. | Child matrix reconciled against merged source and tests; explicit final receipt. |
| #208 | safety architecture | P2 | new quality milestone | General dead-letter/quarantine abstraction; broad error-path scope. | Typed ownership design, bounded content policy, failure-injection tests, full CI, merged PR. |
| #207 | security audit finding | P1 | new quality milestone | Overlaps #219; retain until the implementation evidence exists. | #219 implementation merged, first reviewed PDG report, explicit closure comment. |
| #205 | quality epic | P2 | new quality milestone | Parent for #212–#214 and related complexity slices. | Child scope matrix and merged split receipts; no closure from line-count reduction alone. |
| #204 | architecture audit finding | P2, manual-review | new quality milestone | PR #216 reportedly fixed four original cycles; #240 tracks later findings. | Rebuild exact-current import graph, map residual cycles to issues, merge fixes, attach final zero/residual receipt. |
| #193 | v2.1 architecture/product | P4, manual-review | `v2.1.0 — Memory & Logseq DB Safe-Sync` | Broad OKF evaluation; #402 is the current implementation programme. | #402 accepted and merged, evaluation conclusions documented, remaining scope explicitly split or closed. |

## Relationship decisions

No issue is safe to close from title similarity alone.

- **#207 and #219:** treat #207 as the finding and #219 as the likely canonical
  implementation. Close #207 only after #219 has produced a reviewed baseline and merged
  enforcement policy.
- **#205 and #212–#214:** retain the parent/child hierarchy. Child merges do not
  automatically prove the full parent objective.
- **#204 and #240:** do not merge or close based on the historical cycle lists. Rebuild
  the exact-current import graph first and reconcile each residual cycle.
- **#334, #205, and #212:** coordinate boundaries to prevent overlapping daemon refactors.
- **#193 and #402:** #402 now carries actionable dual-layer implementation criteria.
  #193 remains an evaluation parent until the accepted #402 outcome proves what, if
  anything, remains.

## Phased remote-mutation plan

Each phase is independently reversible and requires explicit authorization.
Every phase begins with the revalidation commands above and stops on drift.

### EX-19B — Establish the successor metadata vocabulary

Allowlist:

- create milestone `v2.1.x — Engineering Quality & Security`;
- create labels `priority:P1` through `priority:P4` and `manual-review`;
- do not modify issues, pull requests, branches, releases, or repository settings.

Verify by re-reading exact milestone and label identifiers. Roll back by deleting only
new, unused metadata if the maintainer rejects the vocabulary.

### EX-19C — Classify contributor-ready issues

Allowlist: #220–#223, #225–#232, and #234–#236. Assign the new quality milestone and
`priority:P3`; preserve existing labels and bodies. Do not close issues.

Verify that exactly 15 issues changed and every other issue is byte-for-byte unchanged at
the metadata fields in scope.

#### EX-19C shipped-evidence correction

A later exact-source revalidation found that #220, #221, #222, #225, #226, #228, #232,
and #234 already have implementing commits on the default branch. They must not be
classified into a new milestone merely because their GitHub state remained open. Their
target-specific evidence, file-level caveats, and separate closure authorization gate are
recorded in
[`CONTRIBUTOR_READY_CLOSURE_AUDIT_2026-08-08.md`](CONTRIBUTOR_READY_CLOSURE_AUDIT_2026-08-08.md).

Before executing EX-19C, remove any issue proven closure-ready by that accepted audit from
the classification allowlist. Do not infer the disposition of #223, #227, #229–#231,
#235, or #236 from this correction.

### EX-19D — Reconcile security and structural findings

Allowlist: #204, #207–#209, #219, #240, #333, and #334. Add priority, milestone, and
dependency notes only after current evidence is attached. #333 requires an explicit
stable-blocker decision. Do not close any issue in this phase.

### EX-19E — Reconcile module parents and OKF evaluation

Allowlist: #205, #212–#214, and #193. Preserve parent/child distinctions. Move #193 to
the existing v2.1 product milestone only after recording its dependency on #402. Do not
close it until #402 acceptance is proven from merged source.

### EX-19F — Retire historical milestones

Only after every remaining open issue has a verified successor milestone:

- close `v1.9.10 — Concurrency & Data Integrity` after confirming its zero-open count;
- migrate the four open v1.9.11 issues and three open v1.9.12 issues through a separately
  reviewed allowlist;
- close v1.9.11 and v1.9.12 only when their open counts are zero.

## Release and Gate B boundary

This audit changes no runtime code, package, lockfile, workflow, Gate B evidence, tag,
release, publication, branch protection, or issue metadata. A metadata classification
cannot qualify or disqualify a release. Any issue proposed as a v2.0 blocker requires an
explicit stable-release decision backed by source, test, and exact-artifact evidence.

## Acceptance receipt for EX-19A

EX-19A is complete only when this ledger and its source dossier update pass the
documentation inventory and knowledge-bundle checks, the changed-file allowlist is
verified, and the accepted commit is recorded. No changelog entry is required because
the slice changes repository governance documentation only.
