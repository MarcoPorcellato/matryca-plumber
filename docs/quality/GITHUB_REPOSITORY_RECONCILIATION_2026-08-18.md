---
type: Audit
title: GitHub and repository reconciliation — 2026-08-18
description: Exact-head reconciliation of Matryca Plumber code, maintained documentation, GitHub planning metadata, and open delivery state.
resource: docs/quality/GITHUB_REPOSITORY_RECONCILIATION_2026-08-18.md
tags: [quality, github, documentation, governance, release, audit]
timestamp: 2026-08-18T00:00:00Z
status: stable
classification: active
last_verified: 2026-08-18
audience: [maintainer, contributor, operator]
owner: quality
authority: evidence
execution_mode: read-only-audit
source_repository: MarcoPorcellato/matryca-plumber
source_ref: main
source_commit: bfac3fd4e3e685582fbcb1c7dbbbdd150bc22191
related:
  - ISSUE_CONTROL_PLANE_2026-08-08.md
  - AGENTIC_MEMORY_GRAPH_OUTCOME_EVALUATION_PLAN_2026-08-11.md
  - AGENTIC_MEMORY_LEADERSHIP_PROGRAMME_2026-08-10.md
  - ../knowledge/index.md
---

# GitHub and repository reconciliation — 2026-08-18

## Purpose and authority

This is a point-in-time reconciliation of the public repository and its GitHub
planning surfaces. It records what was verified at the exact source commit and
what remains open. It does not rewrite historical audit records, qualify a new
release, close issues, or authorize runtime work.

The authoritative layers are deliberately separate:

1. `origin/main` and the source tree establish implementation truth.
2. Maintained documentation and its deterministic inventory establish current
   documentation guidance.
3. GitHub issues, pull requests, milestones, labels, and Projects establish
   public execution state.
4. Release and soak records qualify only the exact artifact and commit named by
   each record.

## Exact source and verification receipt

| Check | Result |
| --- | --- |
| Repository | `MarcoPorcellato/matryca-plumber` |
| Branch | `main` |
| Source commit | `bfac3fd4e3e685582fbcb1c7dbbbdd150bc22191` |
| Working tree | Clean in the isolated audit checkout |
| Python | 3.12.13 |
| Full CI | PASS |
| Tests | 1,865 passed; 5 skipped |
| Coverage | 84.27% |
| Documentation bundle | PASS; 0 OKF findings; 0 Matryca quality findings |
| Agent coherence | PASS |
| Public audit-metric policy | PASS; no public local code-audit metrics |
| Generated system prompt | PASS; build hash matches |
| Static analysis | PASS; index refreshed to the exact source commit for this audit |

The full CI result includes formatting, Ruff, mypy, graph-read sandbox,
version consistency, agent coherence, public-metric policy, documentation
checks, generated-prompt validation, and the complete pytest suite. The four
test-process deprecation warnings are non-failing warnings and do not change
the qualification result.

## Documentation reconciliation

### Current and coherent

- The maintained knowledge bundle passes its inventory, OKF v0.2, and Matryca
  quality checks without drift.
- `README.md` accurately describes Markdown as canonical, Shadow DB as derived,
  Strict Read Only as a graph-mutation boundary, external Shadow acceleration,
  block-granular retrieval, and the traffic-light gardening modes.
- The RC2 terminal evidence remains explicitly bound to the `2.0.0rc2` wheel
  and does not imply stable `2.0.0` qualification.
- Historical programme records remain historical. Their original source commits
  are preserved instead of being silently rewritten to the current head.
- The graph-outcome plan correctly preserves the retrieval foundation while
  requiring resettable final-world-state evaluation before write-adjacent,
  procedural, or proactive promotion.

### Current public planning boundary

The public adaptive-retrieval execution structure exists on GitHub:

- parent epic [#505](https://github.com/MarcoPorcellato/matryca-plumber/issues/505);
- child issues [#506](https://github.com/MarcoPorcellato/matryca-plumber/issues/506)
  through [#511](https://github.com/MarcoPorcellato/matryca-plumber/issues/511);
- public project [Human-Governed Adaptive Retrieval](https://github.com/users/MarcoPorcellato/projects/6);
- milestones A1 through B0 and the `adaptive-retrieval` label.

The programme-design PR [#501](https://github.com/MarcoPorcellato/matryca-plumber/pull/501)
is still draft. Therefore #505–#511 are public planning and coordination
metadata; they are not evidence that the draft plan has become canonical
repository guidance, and they do not authorize implementation or release claims.
The plan becomes repository-canonical only after review and merge, followed by
an exact-head documentation check.

## GitHub delivery-state reconciliation

### Open PRs requiring explicit disposition

The current open PR roster includes:

- [#501](https://github.com/MarcoPorcellato/matryca-plumber/pull/501), draft
  adaptive-retrieval programme documentation;
- [#500](https://github.com/MarcoPorcellato/matryca-plumber/pull/500), RC2
  readiness evidence reconciliation;
- [#499](https://github.com/MarcoPorcellato/matryca-plumber/pull/499), draft
  bounded journal-day retrieval;
- Dependabot PRs [#502](https://github.com/MarcoPorcellato/matryca-plumber/pull/502),
  [#503](https://github.com/MarcoPorcellato/matryca-plumber/pull/503), and
  [#504](https://github.com/MarcoPorcellato/matryca-plumber/pull/504);
- benchmark PRs [#463](https://github.com/MarcoPorcellato/matryca-plumber/pull/463)
  and [#464](https://github.com/MarcoPorcellato/matryca-plumber/pull/464);
- the older dependency and beta-preparation PRs [#368](https://github.com/MarcoPorcellato/matryca-plumber/pull/368)
  and [#326](https://github.com/MarcoPorcellato/matryca-plumber/pull/326).

No open PR is treated as merged, release-ready, or canonical merely because its
head exists locally or its issue title resembles shipped work. Each requires
its own current review, CI, scope, and merge decision.

### Issue and milestone hygiene

The new adaptive-retrieval issues have parent links, labels, and dedicated
milestones. Existing v2.0, v2.1, v2.2, v2.3, and historical v1.9 milestones
remain separate and were not collapsed into a new generic bucket.

The repository still contains older open quality and security issues without a
milestone, including the tracked daemon, parser-boundary, import-cycle, and
clean-code follow-ups. They are not silently reassigned here because their
correct destination depends on current implementation evidence and, for some
items, a stable-release blocker decision. This is the remaining metadata batch:

1. revalidate each issue against the exact current source;
2. assign only a reviewed successor milestone;
3. preserve parent/child and finding/implementation distinctions;
4. attach closure evidence before closing anything.

The timestamped [issue-control-plane ledger](ISSUE_CONTROL_PLANE_2026-08-08.md)
remains the historical proposal and snapshot for that work. This reconciliation
is the current starting point; it does not mutate the older snapshot.

## Code and architecture conclusion

The exact-head CI and static review found no justified code patch for this
reconciliation. The current source already contains the relevant Shadow,
Read Only, evidence, graph-outcome, and documentation-control surfaces, and the
tests cover them at the receipt recorded above.

The next implementation work should therefore remain issue-driven:

- finish the RC2 readiness disposition before any stable-release claim;
- review and merge the adaptive-retrieval programme documentation before using
  it as canonical execution guidance;
- build the resettable graph-outcome evidence bridge before enabling
  write-adjacent adaptive behaviour;
- keep Tine interoperability under its existing #490/#494 boundaries;
- reconcile the older unmilestoned issue set through a separately reviewed
  metadata batch.

## Non-goals and preserved boundaries

- No runtime code, dependency, lockfile, tag, release, PyPI artifact, or soak
  evidence was changed by this audit.
- No historical document was rewritten to make its old source commit appear
  current.
- No public claim of universal memory leadership was added.
- No adaptive runtime was enabled.
- No issue was closed solely from title similarity or local implementation
  evidence.

## Acceptance

This reconciliation is complete when this document passes the maintained
documentation gates at the exact source commit, its links remain repository
relative and valid, and GitHub metadata is re-read before every later mutation
batch. Subsequent changes must create a new dated reconciliation or update a
canonical source document with a fresh exact-head receipt.
