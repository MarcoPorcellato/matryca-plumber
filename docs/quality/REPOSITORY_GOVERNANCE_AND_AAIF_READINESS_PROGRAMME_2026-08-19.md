---
type: execution-programme
title: Repository governance and AAIF readiness programme
description: Evidence-first programme for making Matryca Plumber easier to trust, contribute to, operate, integrate, and evaluate after the v2.0.0 stable release.
resource: docs/quality/REPOSITORY_GOVERNANCE_AND_AAIF_READINESS_PROGRAMME_2026-08-19.md
tags: [quality, governance, github, aaif, interoperability, documentation, roadmap]
timestamp: 2026-08-19T00:00:00Z
status: draft
decision_status: accepted
classification: canonical
last_verified: 2026-08-19
stale_after: 2026-11-17
audience: [maintainer, contributor, operator, agent]
owner: quality
authority: roadmap
execution_mode: gated
source_repository: MarcoPorcellato/matryca-plumber
source_ref: origin/main
source_commit: 2724f7504d943da91e2f4e6a6309cac4d0c9fb30
canonical_for: repository.governance-and-aaif-readiness
official_aaif_status: readiness programme; not submitted; not certified
official_okf_spec_version: "0.2"
official_okf_conformance: not_claimed
matryca_quality_profile: transitional
registry_projection: reviewed_only
related:
  - REPOSITORY_GOVERNANCE_AND_AAIF_READINESS_EXECUTION_STATUS_2026-08-19.md
  - REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
  - AGENTIC_MEMORY_LEADERSHIP_PROGRAMME_2026-08-10.md
  - AGENTIC_MEMORY_GRAPH_OUTCOME_EVALUATION_PLAN_2026-08-11.md
  - ISSUE_CONTROL_PLANE_2026-08-08.md
  - ../knowledge/profile.md
  - ../knowledge/documentation-evolution.md
  - ../roadmaps/ROADMAP_V2_PREPARATION.md
---

# Repository governance and AAIF readiness programme

**Programme date:** 2026-08-19
**Repository:** [MarcoPorcellato/matryca-plumber](https://github.com/MarcoPorcellato/matryca-plumber)
**Current source baseline:** `origin/main@2724f7504d943da91e2f4e6a6309cac4d0c9fb30`
**Product baseline:** stable `v2.0.0`, published on 2026-08-18
**Programme status:** accepted planning specification; implementation remains gated by reviewable issues and pull requests

## Executive decision

Matryca Plumber already has the foundation of a serious open-source project: a
stable v2.0.0 release, a local-first Markdown source of truth, a fail-closed
Shadow DB read path, strict read-only controls, durable qualification evidence,
typed Python, automated CI, security scanning, dependency automation, a
structured documentation bundle, and a growing public roadmap.

The next level is not a repository-wide rewrite. The highest-leverage work is to
make the existing quality visible, current, reproducible, and scalable beyond a
single maintainer. This programme therefore treats repository excellence as an
operating system made of five connected surfaces:

1. **Product integrity:** Markdown remains authoritative; derived indexes and
   caches remain disposable; safety and fallback claims stay explicit.
2. **Evidence:** every material claim has an owner, source commit, verification
   date, reproducible command, and a bounded interpretation.
3. **Open governance:** contributors can discover how to help, maintainers can
   triage consistently, and security or release decisions have visible rules.
4. **Interoperability:** Logseq, MCP, Tine, Matryca Knowledge, and future agent
   systems can exchange a small, versioned, vendor-neutral contract.
5. **Community readiness:** the project can present a realistic 6–12 month
   roadmap and an honest adoption, maintenance, and risk posture to the Agentic
   AI Foundation (AAIF) or another neutral ecosystem body.

This is an **AAIF readiness and submission programme**, not a claim of AAIF
membership, approval, certification, or compliance. AAIF review is an external
gate and cannot be satisfied by local CI alone.

## What this document owns

This is the current cross-cutting programme for repository management after
v2.0.0. It consolidates the planning role previously distributed across the
repository excellence study, the agentic-memory programmes, and the issue
control-plane dossier.

The earlier documents remain valuable and are preserved as follows:

| Document | Role after this programme |
| --- | --- |
| `REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md` | Historical broad audit and source evidence; its old counts are not current state |
| `REPOSITORY_EXCELLENCE_MILESTONE_2026-08-08.md` | Historical record of the 34-PR excellence delivery chain |
| `AGENTIC_MEMORY_LEADERSHIP_PROGRAMME_2026-08-10.md` | Specialist benchmark and biological-memory evidence programme |
| `AGENTIC_MEMORY_GRAPH_OUTCOME_EVALUATION_PLAN_2026-08-11.md` | Specialist resettable graph-world and outcome-evaluation plan |
| `ISSUE_CONTROL_PLANE_2026-08-08.md` | Historical metadata reconciliation ledger |
| `docs/knowledge/profile.md` and `documentation-evolution.md` | Current documentation and projection contract |
| This document | Canonical cross-cutting governance, repository-excellence, and AAIF-readiness sequence |

No historical report is to be rewritten merely to make old snapshots look
current. Current mutable facts belong on their owning surfaces and in fresh
evidence receipts.

### Execution ledger and persistent goal

The companion [execution-status ledger](REPOSITORY_GOVERNANCE_AND_AAIF_READINESS_EXECUTION_STATUS_2026-08-19.md)
is the only mutable status authority for this programme. It records the active
source anchor, completed milestones, current branch, verification receipts,
external gates, and the exact resume point. This programme remains the stable
contract; a status update never silently changes its scope, invariants, or exit
evidence.

## Baseline and evidence discipline

### Verified repository state

The live checkout used for this study is not the release authority: local `main`
is six commits behind `origin/main`, and a linked worktree for an active
documentation branch is dirty. Both facts are preserved as working-context
constraints. The active worktree and its three modified documents must not be
removed, reset, or folded into this programme.

The authoritative documentation baseline for this programme is therefore the
exact remote commit recorded in the frontmatter above. Before implementation,
refresh the checkout and repeat the baseline checks on the exact branch used for
each pull request.

### Current strengths

| Area | Evidence observed | Interpretation |
| --- | --- | --- |
| Release | `v2.0.0` is a non-draft, non-prerelease GitHub release; the v2 roadmap records RC2 Gate B and the stable publication | The stable read-path claim has a public release anchor |
| Runtime model | Markdown remains the system of record; Shadow DB is a derived read cache with fallback | The core local-first invariant is clear and defensible |
| Safety | read-only policy, path containment, atomic writes, writer locking, quarantine, and fallback paths exist | Safety is stronger than a typical early-stage agent-memory repository |
| Verification | `make ci`, documentation checks, generated-prompt checks, release workflows, and durable soak evidence exist | The project already has a useful evidence culture |
| Documentation | `docs/knowledge/` has OKF v0.2-compatible structure plus a stricter Matryca quality profile | The projection boundary is explicit and reusable |
| Community health | `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, issue forms, PR template, CODEOWNERS, Dependabot, CI, CodeQL, and release automation exist | The missing work is consistency, freshness, and scale rather than starting from zero |
| Planning | v2.1, v2.2, v2.3, adaptive-retrieval, discovery, and AAIF-readiness milestones exist | The roadmap has material content but needs one dependency-ordered public view |

### Current governance observations

The most important verified weaknesses are:

1. **The planning surface is fragmented.** Several high-quality dossiers exist,
   but a new contributor cannot immediately tell which one is the current
   cross-cutting authority.
2. **Freshness is uneven.** `SECURITY.md` still names the 1.14.x line as
   current even though v2.0.0 is published. Other old reports intentionally
   contain historical counts and must be labeled rather than silently edited.
3. **Maintainer concentration remains visible.** The repository has a CODEOWNERS
   file, but the public operating model does not yet demonstrate a durable
   review path beyond one maintainer.
4. **AAIF evidence is not yet packaged.** The repository has strong ingredients
   for reliability, security, observability, interoperability, and roadmap
   review, but not one public evidence index with explicit gaps and owners.
5. **Interoperability is described more richly than it is contract-tested.** The
   Logseq block model, MCP surfaces, Tine coexistence strategy, and Matryca
   Knowledge projection should converge on a small testable compatibility corpus.
6. **GitHub planning metadata is healthy but needs a maintained view.** The latest
   read-only milestone audit found 70 open issues and no open issue without a
   milestone. Closed v2.0 and v1.9.10 milestones were retired; remaining open
   work spans v2.1–v2.3, adaptive retrieval, discovery, and adoption. These are
   snapshots and must be refreshed before any remote mutation.
7. **Operational evidence is strong but scattered.** Release records, soak
   evidence, quality dossiers, and operator contracts need a stable index so a
   reviewer can reproduce the claim without knowing private history.

### Status vocabulary

Every programme item uses one of these states:

| State | Meaning |
| --- | --- |
| `verified` | Reproduced from an exact source, commit, artifact, or public record |
| `partial` | Some evidence exists, but a required dimension is missing or stale |
| `proposed` | A design or work item, not evidence of implementation |
| `blocked` | A named external, authorization, environment, or artifact dependency prevents progress |
| `external gate` | The decision belongs to GitHub, PyPI, AAIF, a maintainer, or another independent system |
| `historical` | Preserved evidence that must not be interpreted as current behavior |

Never convert `RUNNING`, `unknown`, local-only success, or stale evidence into
`verified`.

## North-star outcome

By the end of this programme, a technically capable external contributor or
neutral reviewer should be able to:

1. understand the product and its non-negotiable safety model from the README;
2. find the current runtime, security, contribution, release, and roadmap
   contracts in three clicks or fewer;
3. reproduce the documented quality and benchmark claims from a pinned commit;
4. open an issue or PR using the correct template, labels, milestone, and
   acceptance contract;
5. understand which data is authoritative, derived, private, historical, or
   externally reviewed;
6. integrate through a small vendor-neutral Logseq/MCP compatibility contract;
7. see what is proven, what is planned, and what remains an external decision;
8. evaluate the project against AAIF-relevant dimensions without being asked to
   trust marketing language.

## Scope and invariants

### In scope

- repository documentation architecture and freshness;
- GitHub issues, labels, milestones, Projects, Discussions, templates, and
  contributor workflow;
- governance, security posture, maintenance model, and community health;
- release, provenance, benchmark, CI, and operational evidence surfaces;
- Logseq, MCP, Tine, and Matryca Knowledge interoperability contracts;
- AAIF readiness mapping, evidence packaging, and submission preparation;
- targeted implementation changes required to make the documented contracts
  true.

### Explicit non-goals

- claiming AAIF certification or acceptance before an official review;
- replacing Markdown with SQLite, a cloud service, or a second system of record;
- a repository-wide Clean Architecture rewrite;
- expanding v2.0.0 stable scope with biological memory or Logseq DB writes;
- mass-moving historical documentation;
- force-pushing `main`, bypassing required checks, or silently closing issues;
- inventing adoption, performance, safety, or interoperability numbers;
- treating a green CI job as a release, benchmark, soak, or AAIF decision.

### Non-negotiable invariants

1. Logseq Markdown remains authoritative for the OG graph.
2. Shadow DB and other indexes remain derived, disposable, bounded, and
   fail-closed.
3. Strict Read Only protects the user graph while permitting explicitly scoped
   external derived-cache work.
4. Every graph mutation retains the existing path, OCC, atomic-write, and
   parser-parity rules.
5. Public documents are in English, maintainer-authored, vendor-neutral, and
   free of assistant/model attribution.
6. Matryca Plumber is the editing origin for its documentation; Matryca
   Knowledge is a reviewed, Git-provenanced projection.
7. Release and qualification decisions require exact source, artifact, runner,
   and terminal evidence.

## AAIF readiness alignment

AAIF publicly describes project review in terms that include technical strength,
broad usefulness, healthy growth beyond one maintainer group, open operation,
quality and adoption, interoperability, observability, security, and a realistic
6–12 month roadmap. AAIF also describes Technical Committee review and later
governance onboarding as external steps. This programme maps Matryca evidence to
those dimensions without treating the mapping as an official checklist.

| AAIF-relevant dimension | Existing evidence | Current status | Required next proof |
| --- | --- | --- | --- |
| Technical strength and usefulness | Stable v2.0.0, local-first architecture, Shadow DB, Logseq block-level semantics, MCP/CLI surfaces | `partial` | Public architecture brief, reproducible capability matrix, representative user journeys |
| Open operation and governance | License, Code of Conduct, contributing and support docs, issue forms, PR template, CODEOWNERS | `partial` | Maintainer model, decision process, review quorum/backup path, governance page, contributor health measures |
| Security and privacy | `SECURITY.md`, CodeQL, Dependabot, path sandbox, redaction, auth controls | `partial` | Fresh supported-version matrix, threat model, response targets, security evidence index, reviewed disclosure process |
| Reliability and accuracy | CI, fallback semantics, durable Gate B evidence, release records, tests | `verified` for bounded v2.0 read-path claims; `partial` overall | Public evidence index, failure-mode matrix, recovery and corruption test receipts |
| Interoperability | Logseq parser, MCP, Tine strategy, Matryca Knowledge projection, external cache contract | `partial` | Versioned vendor-neutral contract, compatibility corpus, TCK, conformance receipts, consumer examples |
| Observability and traceability | Provenance records, soak checkpoints, generated docs reports, release workflow | `partial` | Stable schemas, public redacted receipts, evidence retention/indexing policy |
| Adoption and ecosystem value | Public repository, releases, README, discussions, issue history | `not evidenced` as a measured claim | Reproducible, privacy-safe adoption signals and user/consumer evidence; never inflate metrics |
| 6–12 month roadmap | v2.1/v2.2/v2.3 and adaptive-retrieval milestones | `partial` | One dependency graph, owners, measurable milestones, explicit external dependencies |
| Community beyond one maintainer group | Contributor history and public discussions | `partial` | Reviewable contributor path, delegated ownership, triage rota, accepted external contributions |

### AAIF-facing deliverable

Create one public `AAIF_READINESS.md` or knowledge concept only after the
evidence index exists. It must contain:

- a one-page project summary;
- the stable product boundary and non-goals;
- architecture and interoperability diagrams;
- security, privacy, and threat-model links;
- release and evidence reproducibility links;
- governance and contribution rules;
- roadmap and dependency graph;
- adoption evidence with collection method and limitations;
- an explicit gap register and external-gate section;
- a request for review, not a claim of approval.

## GitHub operating model

### Repository entry points

The README should remain concise and human-first. It should point to one owner
for each mutable topic:

| User question | Owning surface |
| --- | --- |
| What is Matryca Plumber? | `README.md` |
| How do I install and operate v2.0.0? | README quickstart and the v2 operator contract |
| What is secure or supported? | `SECURITY.md` and `SUPPORT.md` |
| How do I contribute? | `CONTRIBUTING.md`, templates, and the issue control model |
| What changed? | `CHANGELOG.md` and release notes |
| What is planned? | This programme plus the product roadmaps |
| What is proven? | Quality evidence index and release records |
| How does documentation work? | `docs/knowledge/profile.md` and `documentation-evolution.md` |
| How can another project integrate? | Versioned interoperability contract and TCK |

Duplicate prose should be replaced with a short summary and a link. Historical
documents should retain their original context and date.

### Issues, labels, milestones, and Projects

Use GitHub issues for one problem, decision, or deliverable. Every substantive
issue must contain a problem statement, current behavior, proposed outcome,
scope/non-goals, acceptance criteria, dependencies, evidence plan, and a
changelog decision where relevant.

Recommended metadata rules:

- exactly one primary work type (`bug`, `feature`, `documentation`, `research`,
  `governance`, or `maintenance`);
- priority is separate from work type (`P0`, `P1`, `P2`, `P3`);
- a milestone expresses target sequencing, not a promise of delivery;
- an epic links to child issues and owns the outcome, not every implementation
  detail;
- questions and discussions should not be forced into implementation issues;
- closed historical milestones remain closed; do not reopen them to make current
  work look tidy;
- all open actionable issues retain a milestone or are explicitly marked as
  discovery/backlog with a reason;
- use a Project for cross-milestone workflow state (`Backlog`, `Ready`, `In
  progress`, `Blocked`, `Review`, `Done`), while milestones represent release or
  programme outcomes;
- archive stale views, not evidence; keep one public roadmap view and one
  maintainer execution view.

Proposed current programme containers:

| Container | Purpose |
| --- | --- |
| `v2.1.0 — Memory & Logseq DB Safe-Sync` | Product evolution after stable read-path release |
| `v2.2.0 — Hybrid Recall & Memory Curation` | Retrieval and curation capabilities |
| `v2.3.0 — Procedural Memory & Trusted Proactivity` | Write-adjacent and proactive capabilities after gates |
| Adaptive Retrieval milestones | Evidence-driven retrieval research and implementation |
| `Discovery & Convergence` | Uncommitted research and cross-system discovery |
| `Adoption & AAIF Readiness` | Governance, interoperability, evidence, and external review preparation |
| `TCK & Implementations`, `Interoperability & Governance`, `Normative Contract` | Future contract-building containers; keep empty until concrete issues are ready |

Do not create duplicate issues for existing epics. Link slices under the owning
epic and keep the issue control-plane record as a dated audit, not as a second
source of truth.

### Pull requests and protected main

Every implementation PR should have:

- exact base and head SHA recorded before review;
- a narrow diff and explicit non-goals;
- focused tests plus the relevant repository gate;
- documentation and changelog impact decisions;
- review threads resolved by the reviewer, not merely hidden by a new commit;
- fresh terminal CI after retargeting a stacked PR;
- signed squash merge according to protected-main rules;
- deletion of only the merged PR branch;
- no force-push to `main` and no unrelated cleanup in the same PR.

Stacked PRs are acceptable when each child has one purpose and its base is
retargeted and requalified after the parent merge. Stop on conflicts, changed
scope, unexpected skips, failed checks, or new review requests.

### Discussions

Use Discussions for proposals, announcements, interoperability coordination,
and questions that benefit from community context. Convert an accepted proposal
into one issue or epic with a decision record; do not leave implementation scope
only in a discussion reply.

## Interoperability and conformance strategy

The project should turn its conceptual ecosystem into a small, stable contract
before adding more integrations.

### Contract layers

1. **Logseq OG semantic layer:** block identity, indentation, properties,
   namespaces, page boundaries, CRLF/frontmatter behavior, and block-level
   provenance.
2. **Repository layer:** Markdown source-of-truth, read-only cache semantics,
   OCC, atomic writes, external cache location, and failure/fallback states.
3. **Tool layer:** CLI/MCP operation names, typed inputs/outputs, authorization,
   error classes, and capability discovery.
4. **Evidence layer:** schema version, source commit, parser version, corpus
   digest, environment, expected result, and receipt digest.
5. **Consumer layer:** Tine, Matryca Knowledge, Logseq parser, and future
   collaborators consume the contract without acquiring ambient write authority.

### Test Compatibility Kit (TCK)

The proposed TCK should be provider-free and small enough to run locally:

- a provenance-recorded corpus of pages and blocks;
- fixtures for nesting, properties, namespaces, aliases, CRLF, frontmatter,
  malformed input, and concurrent edits;
- read-only parity tests for Markdown and Shadow paths;
- mutation refusal tests for Strict Read Only and Tine-open scenarios;
- parser round-trip and block-identity tests;
- capability and error-contract tests for CLI/MCP consumers;
- a machine-readable result schema and a human-readable summary;
- compatibility levels (`read`, `safe-derived-cache`, `closed-writer`, and
  `concurrent-writer-not-supported` until proven).

The TCK must not imply that passing a parser fixture proves safe concurrent
mutation. That remains a separate deterministic conflict qualification.

## Evidence, benchmark, and release model

### Evidence index

Create a generated or hand-maintained index with one row per public claim:

| Field | Requirement |
| --- | --- |
| Claim ID | Stable identifier, e.g. `V2-SHADOW-READ-001` |
| Claim | Plain-language statement with bounded scope |
| Owner | Maintainer area or named contributor group |
| Authority | Source path, issue, release, or external contract |
| Source commit | Exact Git commit or artifact digest |
| Method | Command, workflow, TCK, benchmark, or review protocol |
| Result | PASS, FAIL, PARTIAL, BLOCKED, or NOT_ASSESSED |
| Verified at | ISO timestamp/date |
| Expiry | Review date or stale-after date |
| Limitations | What the evidence does not prove |
| Public artifact | Redacted receipt, report, or link |

Receipts must never include credentials, absolute private paths, raw secrets,
unbounded logs, or user graph content. Keep sensitive evidence private and link
only to a redacted public summary.

### Benchmark claim policy

- separate retrieval quality, graph outcome, safety, latency, memory, and
  convergence metrics;
- pin corpus, parser, model, environment, and source/artifact digests;
- report p50/p95/p99 where latency matters, plus RSS/high-water memory;
- include correctness and fallback parity in every optimization run;
- use holdouts and negative controls for agentic-memory claims;
- label synthetic, replay, real-vault, and external benchmark evidence
  separately;
- never promote a local benchmark into a public product claim without a retained
  receipt and review.

### Release claim separation

The following remain independent gates:

1. source tests and static checks;
2. package build and installed-wheel verification;
3. benchmark qualification;
4. durable soak and restart/recovery evidence;
5. security review;
6. GitHub Release and PyPI publication;
7. post-release observation;
8. AAIF or other external review.

## CI, local execution, and resilience

The repository should preserve its cost-aware approach while making resource
admission an explicit contract:

- fast targeted checks on every PR;
- full CI on protected merge paths;
- scheduled cross-platform, benchmark, and soak jobs;
- exact artifact and runner binding for qualification;
- local OrbStack/commit-preflight admission before expensive runs;
- fail-closed behavior on `Unknown` or `Deny` resource state;
- serialized or bounded parallelism for memory-heavy tasks;
- durable checkpoints and attempt chains for long-running work;
- no credit for downtime, setup time, preflight time, or stale evidence;
- a public runbook that explains how to resume after a reboot without deleting
  evidence.

The `commit-ci-preflight` repository and installed macOS v3 policy are supporting
infrastructure, not a substitute for Matryca's own source and release gates.
When a policy or image changes, record the exact contract and preserve old
receipts as historical evidence.

## Dependency-ordered execution plan

### Phase 0 — Freeze and refresh the baseline

**Goal:** make the programme executable without disturbing active work.

Deliverables:

- refresh local `main` from `origin/main` in a clean, disposable context;
- preserve all active worktrees, dirty files, soak roots, caches, and receipts;
- rerun repository instructions and deterministic documentation checks;
- refresh GitHub issues, milestones, open PRs, rulesets, Discussions, and release
  metadata read-only;
- update this document's baseline only from the exact refreshed source.

Exit gate: a dated baseline receipt with exact source SHA, clean/dirty status,
worktree inventory, GitHub snapshot timestamp, and check results.

### Phase 1 — Documentation authority and freshness

**Goal:** make the repository understandable and remove contradictory current
claims without rewriting history.

Deliverables:

- correct the supported-version table in `SECURITY.md` to match the stable
  release policy;
- add successor/evolution notices to older planning dossiers where needed;
- keep `docs/knowledge/inventory.*` synchronized through the documented checks;
- create the evidence index and current documentation map;
- check README links, diagrams, release links, and operator paths;
- keep all public documents in English and vendor-neutral.

Exit gate: `make agents-check`, `make docs-check`, link validation, and a manual
human-first README review pass on the exact PR head.

### Phase 2 — Open governance and contributor scale

**Goal:** make healthy external contribution possible beyond one maintainer.

Deliverables:

- publish a concise governance/decision model;
- document maintainer areas, backup reviewers, security escalation, and release
  authority without inventing people or promises;
- review CODEOWNERS and add only real, consenting ownership;
- add contributor pathways for documentation, tests, TCK fixtures, triage, and
  research;
- define issue triage cadence and stale/disposition policy;
- ensure templates collect acceptance, scope, evidence, and non-goals.

Exit gate: at least one external contributor can follow the path from issue to
reviewable PR using public docs; no governance claim is made without an owner.

### Phase 3 — Interoperability contract and TCK

**Goal:** turn ecosystem intent into a minimal testable boundary.

Deliverables:

- publish the versioned semantic and tool contract;
- build the corpus and TCK described above;
- qualify read-only coexistence with Tine;
- qualify Matryca mutations only while Tine is closed;
- keep concurrent mutation unsupported until deterministic conflict tests pass;
- document Matryca Knowledge as a reviewed projection, not an origin;
- publish consumer examples for parser, CLI, MCP, and external cache behavior.

Exit gate: reproducible TCK report with exact corpus/parser/source digests and
explicit unsupported cases.

### Phase 4 — Outcome evaluation and research quality

**Goal:** prevent retrieval-only metrics from overstating agentic-memory value.

Deliverables:

- execute the accepted resettable graph-world plan;
- separate retrieval, action protocol, final-world-state, safety, and efficiency
  metrics;
- retain holdouts, negative controls, provenance, and comparability records;
- map results to product milestones only after review;
- keep experimental features outside the stable contract until their gates pass.

Exit gate: an auditable report that distinguishes what improved, what did not,
and what the experiment cannot establish.

### Phase 5 — CI, release, and operator excellence

**Goal:** make expensive and public operations repeatable and resilient.

Deliverables:

- document fast, full, scheduled, benchmark, soak, and release gates;
- enforce resource admission for OrbStack and long-running local qualification;
- retain exact artifact/runner/provenance receipts;
- add public release evidence summaries and post-release observation windows;
- test reboot, interruption, stale checkpoint, disk pressure, and service restart
  recovery without deleting evidence;
- review workflow permissions, pinning, artifact retention, and expected skips.

Exit gate: a fresh dry-run or documented proof for each operator path, with no
ambiguous `Unknown` or historical evidence treated as success.

### Phase 6 — Targeted product and architecture improvements

**Goal:** implement only changes justified by evidence.

Priority order:

1. stale or unsafe read-only startup behavior;
2. Shadow freshness and generic failure invalidation;
3. X-Ray and query-only contract boundaries;
4. watcher backpressure, quarantine rehabilitation, and checkpoint bounds;
5. measured BM25/Shadow/convergence optimization;
6. AST-enforced dependency direction and narrow module seams;
7. property and mutation tests for safety-critical pure functions.

Every slice is a separate issue and PR unless the dependency graph proves that a
small pair must move together. No broad rewrite is authorized by this programme.

### Phase 7 — AAIF submission package

**Goal:** prepare an honest, reviewable external submission.

Deliverables:

- public AAIF readiness document;
- evidence index and gap register;
- architecture, security, interoperability, governance, and roadmap briefs;
- contribution and maintenance model;
- adoption evidence with methodology and limitations;
- list of external dependencies and questions for the AAIF Technical Committee;
- final maintainer review and explicit submission decision.

Exit gate: the package is internally consistent, all claims link to evidence,
open gaps are visible, and the maintainer explicitly chooses whether to submit.

## Prioritized work register

### P0 — Make the current project trustworthy to an external reviewer

| ID | Work item | Why now | Evidence of completion |
| --- | --- | --- | --- |
| P0-01 | Establish this programme as the cross-cutting authority | Prevent plan drift and duplicate roadmaps | Linked successor notes and current navigation map |
| P0-02 | Refresh security support policy for v2.0.0 | A stale supported-version claim undermines trust | Reviewed `SECURITY.md`, tests/links, changelog decision |
| P0-03 | Publish the evidence index | Make release, safety, benchmark, and docs claims auditable | Schema-validated public index with receipts and limitations |
| P0-04 | Publish governance and maintainer model | AAIF readiness requires open operation beyond one person | Governance page, backup path, ownership review |
| P0-05 | Reconcile current GitHub roadmap | Make milestones, Projects, issues, and Discussions tell one story | Fresh snapshot, disposition ledger, no duplicate epics |

### P1 — Make integration and evaluation reproducible

| ID | Work item | Why next | Evidence of completion |
| --- | --- | --- | --- |
| P1-01 | Version the vendor-neutral interoperability contract | Prevent ad hoc integration promises | Contract document, schema, compatibility levels |
| P1-02 | Build the Logseq/MCP/Tine TCK | Convert compatibility claims into tests | Corpus digest, machine report, unsupported-case list |
| P1-03 | Publish public redacted release/soak evidence | Make reliability claims inspectable | Stable evidence summaries and retention policy |
| P1-04 | Complete graph-outcome evaluation | Measure memory usefulness beyond retrieval | Reproducible outcome report and holdout policy |
| P1-05 | Harden CI/resource runbooks | Reduce failed or unsafe expensive runs | Admission/runbook receipts and interruption tests |
| P1-06 | Improve contributor onboarding | Reduce maintainer-only knowledge | First-contribution path and reviewed examples |

### P2 — Make quality scale with the codebase

| ID | Work item | Evidence threshold |
| --- | --- | --- |
| P2-01 | Enforce architecture boundaries with AST/static checks | Current-source proof plus no unexplained exemptions |
| P2-02 | Split oversized behavior seams | Focused tests and unchanged public contracts |
| P2-03 | Add property/mutation tests | Bounded safety-critical coverage and retained results |
| P2-04 | Establish performance regression budgets | Representative p99/RSS/convergence baselines |
| P2-05 | Add privacy-safe adoption signals | Collection method, limitations, and no inflated claims |
| P2-06 | Establish recurring documentation freshness review | Deterministic report and named owner |

## Standard issue and PR contract

Every implementation item created from this programme must include:

```markdown
## Problem Description
## Current Evidence
## Proposed Outcome
## Scope and Non-Goals
## Files, Surfaces, and Owners
## Dependencies
## Acceptance Criteria
## Verification Commands and Receipts
## Security, Privacy, and Compatibility Impact
## Documentation and Changelog Decision
## Rollback or Rejection Conditions
```

The issue must identify the milestone, priority, work type, parent epic when
applicable, and whether the result is product, evidence, governance, or external
gate work. The PR must repeat the exact scope, base/head SHAs, tests, and changed
public claims.

## Cost-aware delegation and recovery

Routine, bounded work may be delegated to a lower-cost model or deterministic
tool: inventory collection, link checking, issue-body consistency, test execution,
receipt formatting, and draft documentation comparison. The primary maintainer
review retains architecture, security, release, scientific interpretation,
public claims, and final integration.

Every delegated task must return:

- exact repository and commit;
- files inspected or changed;
- commands and exit status;
- unresolved uncertainty;
- evidence paths or hashes;
- a recommendation separated from observed facts.

Long-running work must persist a small status ledger with current phase, last
verified commit, active branch/PR, completed gates, next action, and stop reason.
On interruption or reboot, resume from the ledger and revalidate the exact
artifact and source binding. Never delete a checkpoint to make a run appear fresh.

## Completion checklist

The programme is complete only when all applicable boxes are verified:

- [ ] this programme is linked from the documentation entry point;
- [ ] older plans have explicit historical/specialist roles;
- [ ] current release and security claims are fresh and consistent;
- [ ] governance, contribution, support, and security surfaces are coherent;
- [ ] CODEOWNERS reflects real, consenting ownership and a backup path exists;
- [ ] GitHub issue, milestone, Project, and Discussion navigation is reconciled;
- [ ] the evidence index is schema-valid, redacted, reproducible, and current;
- [ ] the interoperability contract and TCK have exact provenance;
- [ ] unsupported concurrent-write and other non-goals are explicit;
- [ ] graph-outcome evaluation separates retrieval from final-world-state claims;
- [ ] CI, resource admission, release, soak, and recovery paths are documented;
- [ ] targeted product improvements have focused tests and changelog decisions;
- [ ] public docs remain English, vendor-neutral, and maintainer-authored;
- [ ] AAIF readiness is mapped with gaps and external gates visible;
- [ ] the maintainer has made an explicit submit/not-submit decision.

## Final guardrails

The repository becomes “stellar” by being unusually clear about what it knows,
what it guarantees, what it refuses, and how another person can verify it. The
programme therefore prefers small reviewable changes, durable evidence, honest
limitations, and a navigable public operating model over volume of features or
marketing claims.

The stable v2.0.0 release is the foundation. The next milestone is not to make
the repository look complete; it is to make every important claim independently
checkable and every future contribution safer to integrate.

### Official references

- [AAIF — Submit a Project](https://aaif.io/submit-a-project)
- [AAIF — official organization and Technical Committee](https://github.com/aaif)
- [GitHub — About milestones](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/about-milestones)
- [GitHub — Milestone administration](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/creating-and-editing-milestones-for-issues-and-pull-requests)
- [GitHub — Projects best practices](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/best-practices-for-projects)
- [GitHub — Administering issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/administering-issues)
