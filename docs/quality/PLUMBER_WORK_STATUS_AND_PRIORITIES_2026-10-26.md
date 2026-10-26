# Matryca Plumber: work status and priorities — 26 October 2026

This is a dated research and planning snapshot, not a release, compatibility
admission, delivery schedule or replacement backlog.

- **Reviewed source:** [`905a6c6a57ca9173becc9b8df78d2051557abcd7`](https://github.com/MarcoPorcellato/matryca-plumber/commit/905a6c6a57ca9173becc9b8df78d2051557abcd7).
- **Review date:** 26 October 2026.
- **Coverage:** 80 open issues, four open dependency pull requests, current release
  records and the relevant source, decisions and implementation plans.
- **Selected next focus:** predictable dashboard reads on large Markdown graphs.
  The other opportunities below remain proposals, not delivery commitments.

The [public roadmap](../../ROADMAP.md) provides navigation. Existing issues remain
the operational work records; this document does not create a second checklist
or authorize implementation, publication or access to private graphs.

## Current state

| Status | What it means today |
| --- | --- |
| Available: stable | [`v2.0.0`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0) remains the default stable release recommendation. |
| Available: experimental | [`v2.1.0-alpha.3`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.1.0-alpha.3) was published on 23 October 2026. Publication is not full 2.1.0 qualification. |
| Restricted experimental evidence | The original alpha.3 wheel has [public consumer evidence](https://github.com/MarcoPorcellato/matryca-trama/blob/b530071f808a044f09c33a791278669c52824f48/docs/status/receipts/2026-10-24-og-alpha3-consumer-qualification.md) for an exact synthetic-only OG producer/consumer tuple. It does not establish general real-vault, Logseq-version-range, native DB or operating-system isolation support. Packaged proposed/unqualified labels remain unchanged. |
| Reviewed, not released | [Parser PR #267](https://github.com/MarcoPorcellato/logseq-matryca-parser/pull/267), head `28584d9461ebac8769939bd0c45aa88cb7fbea46`, is open at this snapshot. All 14 hosted checks pass. The change is not yet a corrected published Parser package or a Plumber integration. |
| Open incident | [Dashboard issue #656](https://github.com/MarcoPorcellato/matryca-plumber/issues/656) remains unresolved. [PR #659](https://github.com/MarcoPorcellato/matryca-plumber/pull/659) corrected read-only/bootstrap guidance, not the dashboard hang. |
| Blocked: native DB | [Issue #491](https://github.com/MarcoPorcellato/matryca-plumber/issues/491) records terminal qualification blockers for the permitted official DB transports. This review establishes no Logseq DB compatibility. |

The accepted [RC4-to-2.1.0 supersession decision](RC4_TO_V2_1_0_SUPERSESSION_2026-10-16.md)
ends the 2.0.1 line at RC3 and transfers outstanding full-release obligations to
the 2.1.0 programme under [#582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582).
Historical candidates, failed attempts, tags and evidence remain preserved.
Experimental publication and the separately governed full qualification/soak
campaign must not be conflated.

## Selected next focus: predictable dashboard reads

The practical goal is a dashboard request that completes within declared bounds
or fails clearly, with controlled work after cancellation. A caller timing out
does not prove that background work has stopped.

The Parser improvement removes repeated ownership scans by building a temporary
index for each attached-node read. Its source checks cover aliases, collision
filtering, node order, path failures and coordinated reloads. It introduces no
persistent ownership cache. It does **not** fix reference fallback or whole-request
cancellation, and its green CI does not prove deployed dashboard performance.

The next dependency-ordered steps are:

1. Complete the Parser change and authenticate the corrected released package
   through the separate merge and release gates.
2. Select the corresponding Plumber dependency profile and qualify the integration
   while preserving the immutable alpha.3 producer, wheel, dependency closure and
   historical fingerprints.
3. Qualify a bounded synthetic dashboard case, including lifecycle and cancellation
   evidence. State separately what remains unresolved in reference fallback,
   bootstrap/Shadow status and recovery.

No end-to-end fix is claimed until those checks exist. Increasing the client
timeout alone is not an acceptance criterion. No private graph access follows
from this planning snapshot.

## Opportunities reviewed

Effort below is relative and preliminary, not a time or cost estimate. An open
issue does not prove that all of its requested functionality is absent.

| Opportunity | Status and practical value | Smallest useful next result | Relative effort |
| --- | --- | --- | --- |
| Dashboard and Parser integration — [#656](https://github.com/MarcoPorcellato/matryca-plumber/issues/656) | Selected next focus; make large-graph reads predictable. | An authenticated Parser integration and one bounded dashboard/lifecycle qualification, without claiming the entire incident solved prematurely. | Medium; high integrity risk |
| Bounded operational diagnostics — [#391](https://github.com/MarcoPorcellato/matryca-plumber/issues/391) | Proposed supporting slice; distinguish slow work, failure and completed cleanup. | Reuse existing diagnostics and expose duration, phase, outcome and final work state for one path, without private content or unbounded labels. | Medium |
| Reproducible memory baseline — [#587](https://github.com/MarcoPorcellato/matryca-plumber/issues/587), [#588](https://github.com/MarcoPorcellato/matryca-plumber/issues/588) | Proposed; measure quality before adding more retrieval mechanisms. | Map acceptance criteria onto the existing benchmark contracts and runner, then close only the gaps needed for one reproducible baseline. | Medium |
| Hermes memory workflow — [existing guide](../integrations/hermes-agent.md) | Proposed; make supported memory operations easier to use correctly. | A verified read-only workflow with explicit error handling. Any write/update extension uses governed Plumber surfaces and a separate approval; no direct vault writer or automatic consolidation. | Small to medium |
| Page-link capability for larger graphs — [#654](https://github.com/MarcoPorcellato/matryca-plumber/issues/654) | Proposed new Plumber capability; not a replacement for the admitted topology profile. | A bounded page-level producer contract and synthetic fixtures. The initial R1/R2 scope includes recognized page references in properties; tags remain distinct and no property-value payload is implied. | Large |
| Additive payload reads — [accepted payload design](../decisions/2026-09-12-plumber-graph-payload-read-v1.md) | Proposed contract work, not a new framework or evidence of DB support. | Reconcile the payload design with existing `plumber.graph.read/v1`, then complete the remaining schema, negative fixtures and static TCK. | Medium |
| Release and backlog clarity — [#582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582), [#385](https://github.com/MarcoPorcellato/matryca-plumber/issues/385) | Supporting documentation; prevent historical plans from appearing current. | Correct current pointers and classify a small set of tickets as implemented, partial or outstanding, preserving their evidence and history. | Small, timeboxed |
| Native DB reopening decision — [#491](https://github.com/MarcoPorcellato/matryca-plumber/issues/491) | Blocked; strategically important but not an implementation-ready transport. | Decide whether a changed official artifact justifies a new bounded admission gate. A newer upstream build is not proof that an old blocker is fixed. | Small for the decision; potentially large for qualification |

### Work that should be reused, not rebuilt

The repository already contains
[`benchmark_protocol.py`](../../src/memory/benchmark_protocol.py) and
[`retrieval_runner.py`](../../src/memory/retrieval_runner.py). Retrieval quality,
end-to-end answer quality, structural fidelity, abstention, latency and resource
use remain different measurements. One score must not become a general product
claim. Dataset provenance, licenses and any external comparator boundary need
their own checks.

Diagnostics should precede watcher/backlog and checkpoint-resilience changes in
[#398](https://github.com/MarcoPorcellato/matryca-plumber/issues/398) and
[#399](https://github.com/MarcoPorcellato/matryca-plumber/issues/399).
Old performance reports for catalog saves and backlink invalidation need a fresh
bounded baseline before optimization.

Backlog reconciliation should also check partially delivered work, including
[#394](https://github.com/MarcoPorcellato/matryca-plumber/issues/394) and
[#401](https://github.com/MarcoPorcellato/matryca-plumber/issues/401), before treating
their entire scopes as new implementation. This is not permission to close them.

The four open dependency PRs
([#658](https://github.com/MarcoPorcellato/matryca-plumber/pull/658),
[#639](https://github.com/MarcoPorcellato/matryca-plumber/pull/639),
[#610](https://github.com/MarcoPorcellato/matryca-plumber/pull/610),
[#609](https://github.com/MarcoPorcellato/matryca-plumber/pull/609))
need their own compatibility review. This snapshot does not recommend merging
the batches or widening dependency ranges automatically.

## Blocked and deferred work

- **Logseq DB:** previous results remain tied to their exact attempted artifacts.
  MCP HTTP remains blocked while upstream
  [`logseq/db-test#1101`](https://github.com/logseq/db-test/issues/1101) is open.
  Any new admission, fixture provisioning and read qualification are distinct
  attempts. No direct SQLite, DB-to-Markdown fallback, DB-source Shadow,
  events, sync or writes follow from this review.
- **Larger graphs:** a page-level view can reduce transfer volume, but does not
  eliminate Parser work. A graph above the existing 4,096-node topology schema
  ceiling needs a different bounded representation or schema, not just a higher
  descriptor value. No private-vault sizing or new scale measurement is
  published here.
- **Advanced memory:** clustering, adaptive retrieval
  ([#505](https://github.com/MarcoPorcellato/matryca-plumber/issues/505)),
  proactivity, procedural learning and the
  [epistemic layer](https://github.com/MarcoPorcellato/matryca-plumber/issues/559)
  remain separately governed research or implementation programmes.
- **Broad refactors and new gates:** large-module restructuring, advisory lint
  triage and heavier analysis/soak gates need bounded evidence and explicit
  scope. They are not prerequisites for every small product improvement.
- **Trama:** consumer implementation and its maintainer-local experiments are
  coordinated separately. This roadmap update changes neither consumer
  admission nor access to user graphs.

## How progress will be reported

Public updates will distinguish **available**, **reviewed**, **selected next
focus**, **proposed**, **blocked** and **deferred**. Qualification statements will
name the exact artifact, environment and scope instead of implying general
support.

Significant milestones — a merged Parser fix, a corrected release, a Plumber
integration, a qualified bounded case or a resolved blocker — can receive a dated
update in [GitHub Discussions](https://github.com/MarcoPorcellato/matryca-plumber/discussions).
No fixed reporting schedule or automation is created. Issues remain the place
for acceptance criteria and implementation evidence; Discussions explain
direction and invite feedback.

This snapshot preserves the context of the earlier
[interop roadmap discussion](https://github.com/MarcoPorcellato/matryca-plumber/discussions/495)
rather than silently rewriting it. Future corrections should be explicit and
dated. No runtime tests, new benchmark results, package publication or support
admission were produced by this review.
