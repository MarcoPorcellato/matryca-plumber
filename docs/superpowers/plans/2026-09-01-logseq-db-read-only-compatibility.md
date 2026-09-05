# Historical Logseq DB Read-Only Compatibility Implementation Plan

> **Historical/non-authorizing — superseded as execution authority on 2026-09-05.** This document
> is retained unchanged below as historical planning and evidence context. It
> does not authorize a Trama host adapter or `trama.logseq.read/v1` authority,
> production contract, Trama-side session port, or a Logseq DB runtime claim. Current
> authority is the accepted [Plumber Logseq gateway decision](../../decisions/2026-09-05-plumber-logseq-gateway-authority.md).

## Current superseding model

Plumber is the sole Logseq gateway and owner of all public `plumber.*`
contracts. The admitted directions are `Logseq OG -> Parser -> Plumber ->
Trama/Brain` and `Logseq DB official host surface -> Plumber -> Trama/Brain`.
GraphReadPort remains filesystem/Shadow-only. A future public
`GraphSessionReadPort` is Plumber-owned and remains feature-off until an exact
official-host and contract qualification passes. Trama and Brain are consumers
only and do not import Parser. No direct internal-database access or mutation
is authorized.

---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an evidence-backed experimental Logseq DB read path for graph identification, one page read, and one complete block-subtree read, using Matryca Trama as the named companion and adapter product while preserving Matryca Plumber's existing Logseq OG, Shadow DB, Strict Read Only, MCP, and CLI behavior.

**Architecture:** A pinned CLI-first capability spike in Matryca Trama selects one supported Logseq host surface before production adapter code is written. Trama owns the user-facing companion, official Logseq OG/DB adapters, and host-object normalization into the versioned `trama.logseq.read/v1` contract. Matryca Plumber consumes that contract through a new session-bound `GraphSessionReadPort`; its existing filesystem `GraphReadPort` remains the OG/Shadow contract. A separate characterization-first Clean Architecture lane may reduce `get_graph_read_port`, but it must not become a DB prerequisite or widen the filesystem port. Matryca Brain remains optional and outside this read path. Events, DB-source Shadow acceleration, all DB writes, and Trama–Brain connection remain separate gated programmes.

**Tech Stack:** Matryca Trama Python 3.12+ packages, pytest, Pydantic-free Plumber boundaries, official Logseq CLI first, official Logseq JS Plugin SDK second, MCP stdio only as a third probe, JSON fixtures, GitHub Actions, Matryca documentation profile v1.0 over OKF v0.2.

**Spec:** [`docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md`](../../roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md)

## Global Constraints

- Start from public `main@12ca79cb14f9bbdf196ec409a48025afb6503ca1`; revalidate GitHub `main` before every branch.
- Use short-lived branches from current `main`; every PR targets `main`, carries one reviewable concern, and merges before a dependent branch is cut.
- Never commit directly to `main` and never use a long-lived integration branch.
- Never open, query, copy, export as an implementation shortcut, or mutate Logseq internal `db.sqlite`.
- Probe supported host surfaces in this order: exact bundled CLI, official plugin SDK, MCP stdio. MCP HTTP is a current NO-GO while upstream issue #1101 remains open.
- Initial product scope is exactly: graph identification, page read, complete ordered block-subtree read.
- The companion product is [Matryca Trama](https://github.com/MarcoPorcellato/matryca-trama). Do not create a second Logseq companion or plugin inside Matryca Plumber.
- Trama owns Logseq-host lifecycle, OG/DB adapters, companion UX, and the host side of shared contracts. Plumber owns memory/search services, agent-facing CLI/MCP behavior, and the consumer-side session router.
- Shared graph/session, DTO, capability, provenance, and error vocabulary must be versioned once and tested from both repositories; neither repository may silently fork the contract.
- Matryca Trama and Matryca Brain remain separate products, repositories, runtimes, caches, release cadences, and licensing surfaces. Trama must never import Brain-private source.
- The initial Logseq DB read path must work without Matryca Brain. Any later Brain connection uses an optional versioned public contract with explicit authentication, graph selection, data flow, revocation, compatibility, licensing, and failure behavior.
- Graph events, DB-source Shadow ingestion, search expansion, properties beyond the selected DTO contract, and all DB mutations are out of the initial scope.
- A DB graph must never silently fall back to an OG filesystem graph.
- Existing OG Markdown parsing continues through `logseq-matryca-parser`; DB objects are normalized from official host DTOs and never passed through filesystem/parser assumptions.
- Source authority is mode-specific: Markdown files remain authoritative for OG graphs; the official Logseq host surface remains authoritative for DB graphs. Trama, Plumber, and Brain must never reinterpret a DB graph as an authoritative Markdown mirror.
- Keep the current filesystem `GraphReadPort` unchanged for OG and Shadow behavior. Do not widen its `Path` boundary to accept Logseq DB sessions.
- Do not make `get_graph_read_port` responsible for DB mode or session routing. Any reduction of that selector uses a separate branch, characterization tests, and unchanged fallback semantics.
- Introduce a distinct session-bound `GraphSessionReadPort` only after the capability spike proves exact graph identity and complete subtree semantics.
- Shadow remains a disposable derived cache for supported sources, never Logseq DB's system of record.
- Unsupported version, missing capability, disconnect, graph switch, foreign binding, stale session, malformed payload, excessive payload, and incomplete subtree must fail closed.
- Existing public GitHub artifacts remain maintainer-authored and contain no assistant or local-tool attribution.
- Standard GitHub-hosted CI is authoritative for both public repositories; do not add CCP receipt requirements.
- Every Plumber documentation PR runs `make docs-inventory-sync`, `make docs-inventory-md`, `make docs-check`, and `make docs-audit`.
- Every Trama PR runs its exact repository-local foundation or implementation gates plus required hosted CI.
- Every code PR runs focused tests first and that repository's full CI before merge.
- Tine Direct Files coexistence is a separate qualification lane. It must not add a Tine-specific adapter to the initial Logseq DB implementation.

---

## Verified Current Anchors — 2026-09-05

| Surface | Exact anchor | Meaning |
| --- | --- | --- |
| Matryca Plumber public main | `12ca79cb14f9bbdf196ec409a48025afb6503ca1` | Current planning base; this refresh starts from that exact commit |
| Matryca Trama public main | `9905e8a36acb83a17a33b702a5fa620d6bfed185` | Named companion with Python-first foundation and qualified synthetic OG contract; no DB-host claim |
| Trama shared contracts | [#2](https://github.com/MarcoPorcellato/matryca-trama/issues/2) | Versioned Parser/Plumber contract track |
| Trama Logseq adapters | [#4](https://github.com/MarcoPorcellato/matryca-trama/issues/4) | OG and initially read-only DB adapter track |
| Matryca Brain public main | `e69a97a8c702a773c9a3ce8307b5a667ed2be1dd` | Current verified Brain source observation; no dependency is introduced |
| Trama–Brain product boundary | [Brain #430](https://github.com/MarcoPorcellato/Matryca-per-Delineat/issues/430), [Trama ADR-0002](https://github.com/MarcoPorcellato/matryca-trama/blob/main/docs/decisions/ADR-0002-TRAMA_BRAIN_PRODUCT_BOUNDARY.md) | Separate products and repositories; optional future public contract |
| Existing strategy | `docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md` | Design authority |
| Logseq application source | `d2ab7726ab74402c14fdbc33041a89ac55c899ae` | Current official `logseq/logseq` `master` observed through GitHub API |
| Logseq documentation | `08f855f24d66e4509b7ea808554c13b4649e6ee1` | Current official `logseq/docs` `master` observed through GitHub API |
| Logseq `db-test` | `f65c01b8f6101a0263ce6a8723fbbb89bc3a3a79` | Current official test repository anchor; not an application release |
| Logseq nightly release | target `dde0aba2d441c962d28989b0af894cc261da3898`; current mutable tag `f7362f07b0cecd1c3ef6e0983c1446868658fb00` | Published 2026-08-26; compatibility evidence binds downloaded asset digest and embedded revision, never the mutable tag alone |
| Logseq macOS arm64 nightly artifact | DMG `ff81dd7513efa080a7f9bd122fca99d82f455a5c6745f154671b7530b8f8379b`; ZIP `f3cbaff017f2063a68583d9ca885aa1e52f1e324df98ea4fcb24c75fee2c244d` | Candidate artifact digests; reverify before acquisition or execution |
| Parser public main and release | `65e8e64f7f0227bcae8235069fbc3da834652744`; `v1.8.2` | Current parser source and release; Plumber's lock still pins `1.7.1`, so dependency refresh is a separate lane |
| Interoperability epic | [#490](https://github.com/MarcoPorcellato/matryca-plumber/issues/490) | Parent programme |
| Capability spike | [#491](https://github.com/MarcoPorcellato/matryca-plumber/issues/491) | First runtime-evidence gate |
| Legacy Plumber companion tracking | [#492](https://github.com/MarcoPorcellato/matryca-plumber/issues/492) | Reconcile with Trama ownership; not authority for a second companion |
| Plumber protocol and threat model | [#493](https://github.com/MarcoPorcellato/matryca-plumber/issues/493) | Consumer-side boundary coordinated with Trama #2 |
| DB read adapter | [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) | Product read vertical |
| DB Safe-Sync writes | [#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) | Explicitly deferred authority gate |
| Tine collaboration | [Discussion #334](https://github.com/martinkoutecky/tine/discussions/334) | Direct Files read-only needs no special adapter |
| Tine external-file safety | [#337](https://github.com/martinkoutecky/tine/issues/337) | Closed completed after Concord work; version-bound evidence, not concurrent-write authority |
| Tine future CLI / MCP | [#108](https://github.com/martinkoutecky/tine/issues/108), [#109](https://github.com/martinkoutecky/tine/issues/109) | Possible future host-authoritative automation surfaces |
| Tine Git integration | [#33](https://github.com/martinkoutecky/tine/issues/33) | Parallel sync/backup feature; not a revisioned mutation protocol |

Current runtime evidence:

- `GraphReadPort` still accepts a filesystem `Path` and provides subtree and spatial-page Markdown reads.
- `MarkdownGraphRepository` and `ShadowGraphRepository` implement filesystem-source behavior.
- Dispatch selects Shadow only when the external cache is healthy; otherwise it uses Markdown.
- Current page dispatch still reads through filesystem/parser behavior, while subtree dispatch uses the filesystem `GraphReadPort`; neither is a Logseq DB session boundary.
- No `GraphSession`, Logseq DB adapter, event cursor, or DB-source Shadow adapter exists.
- Official Logseq documentation still marks DB as beta.
- Official CLI documentation now exposes explicit graph selection, graph metadata, page/block tree reads, and structured output. It also owns a shared `db-worker-node` lifecycle and may replace a revision-mismatched server, so a nominal read command can have process-level side effects that the spike must constrain and record.
- Official plugin SDK exposes graph identity, DB-mode detection, page reads, and child-inclusive block/page reads. Exact completeness, order, and version behavior remain unproven until the pinned spike runs.
- MCP HTTP remains blocked by open upstream issue #1101. MCP stdio is only a third candidate and receives no production claim without the same identity and subtree proof.
- Upstream issues #832 and #833 were closed as completed on 2026-08-31. Closure is not exact-artifact qualification; the spike must reproduce the relevant read semantics against the selected artifact.
- `get_graph_read_port` remains a filesystem selector with two direct production callers (`handle_read_subtree` and the wheel probe). Code-graph orientation rates its transitive blast radius CRITICAL; any simplification stays isolated from DB work.

## Status Vocabulary

- **PROPOSED:** Planned but not started.
- **IN PROGRESS:** One branch owns the slice and no dependent slice has started.
- **PASS:** Exact-head tests and required hosted checks are terminal green.
- **NO-GO:** Evidence proves the selected approach cannot satisfy required boundaries.
- **BLOCKED:** Missing external capability or authority prevents safe progress.
- **DEFERRED:** Explicitly outside the initial read-only scope and not blocking it.

## Trunk-Based Delivery Contract

1. Fetch and verify exact GitHub `main`.
2. Cut one branch from that exact commit.
3. One branch and PR modifies one repository only; cross-repository contracts use separate, explicitly pinned PRs.
4. Keep the diff narrow enough for one reviewer to accept or reject independently.
5. Run focused tests and full required CI.
6. Push and open one PR only under explicit remote authorization.
7. Merge only at unchanged head/base with terminal-green required checks and no unresolved review thread.
8. Delete only the merged remote branch.
9. Fetch the resulting `main` before cutting the next dependent branch.

Independent documentation or research can run in parallel only when files do not overlap. Production adapter work remains sequential because transport selection, protocol, session routing, and page/subtree reads form one dependency chain.

## Historical Local Main Recovery — COMPLETE

The 2026-09-01 recovery below is retained as historical operator evidence, not current checkout state:

- [x] Recorded complete primary-checkout status, branch refs, worktree registrations, and the two dirty diffs.
- [x] Created `recovery/main-dirty-20260901-701b923` from the divergent local `main`.
- [x] Preserved only the two tracked modified files in signed commit `b036d3bdc6c289b3eff37a058fafb1c9d8dec24a`; signature verification passed.
- [x] Verified `.worktrees/human-governed-adaptive-retrieval-plan-20260816` is registered and added only `.worktrees/` to local `.git/info/exclude`.
- [x] Moved local `main` to freshly verified `origin/main@3208bedfaeef0708034089057702cd21fa5dec52`.
- [x] Confirmed local `main` is byte-clean and equals GitHub `main`.
- [ ] Preserve the recovery branch until its owner confirms the two recovered changes have been integrated or abandoned.

Do not use `git reset --hard`, `git clean`, stash, or worktree deletion for this recovery.

**Current planning state (2026-09-05):** the primary checkout is clean at
`3208bedfaeef0708034089057702cd21fa5dec52`, three commits behind
`origin/main@12ca79cb14f9bbdf196ec409a48025afb6503ca1`. Do not move or edit that
checkout as part of this refresh. Use a clean isolated worktree from the exact
remote anchor and revalidate it before every delivery branch.

---

### Task 1: Publish Current Programme Anchors — COMPLETE

**PR scope:** Documentation only. Update the accepted strategy with current upstream pins, the confirmed read-only target, the trunk-based sequence, and this plan link.

**Files:**
- Create: `docs/superpowers/plans/2026-09-01-logseq-db-read-only-compatibility.md`
- Modify: `docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md`
- Modify generated: `docs/knowledge/inventory.json`
- Modify generated: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: existing strategy and verified public/upstream anchors.
- Produces: one public execution authority linking Plumber #490/#491/#492/#493/#17/#25 with Trama #2/#4 and the non-blocking Tine lane.

- [x] **Step 1: Add a dated current-state addendum to the strategy**

Record these exact decisions:

```text
Initial compatibility claim:
- graph identification
- one page read
- one complete ordered block-subtree read

Deferred:
- events and convergence
- DB-source Shadow acceleration
- DB mutation and Safe-Sync

Ownership and parallel lanes:
- Matryca Trama is the single companion and owns official Logseq adapters
- Matryca Plumber owns the consumer session boundary and agent surfaces
- Tine Direct Files read-only coexistence needs no special adapter
- Tine concurrency remains unclaimed; #108/#109 are future host-authoritative candidates
```

- [x] **Step 2: Add exact upstream anchors and drift rule**

Require every executable probe to record Logseq source, SDK/package lock, documentation commit, app build, Trama commit, Plumber commit, graph fixture digest, probe source commit, and raw-result digest. A later upstream version requires a new evidence row; it must not overwrite the old row. Tine qualification additionally records exact release, source commit, Direct Files mode, platform, and proof of zero Matryca graph writes.

- [x] **Step 3: Link this plan from the strategy**

The strategy remains design authority; this file owns execution order and PR boundaries.

- [x] **Step 4: Regenerate documentation inventory**

Run:

```bash
make docs-inventory-sync
make docs-inventory-md
```

Expected: the new plan has one curated inventory entry and generated Markdown matches JSON.

- [x] **Step 5: Run documentation gates**

Run:

```bash
make docs-check
make docs-audit
```

Expected: `docs-check` PASS; `docs-audit` completes as informational evidence.

- [x] **Step 6: Commit the documentation slice**

```bash
git add docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md \
  docs/superpowers/plans/2026-09-01-logseq-db-read-only-compatibility.md \
  docs/knowledge/inventory.json docs/knowledge/inventory.md
git commit -S -m "docs(logseq): plan DB read-only compatibility"
```

Stop before push or PR unless separately authorized.

Merged by Plumber PR #555 as commit
`1673bc0167d5b45e8ce09567f75d86f2f50a302e` on 2026-09-01. The exact
commands above describe the original slice; current execution starts from the
refreshed anchors in this document.

---

### Task 2: Establish Matryca Trama Execution Authority — COMPLETE

**Repository:** `MarcoPorcellato/matryca-trama`

**PR scope:** Documentation and planning only. Name Trama as the only companion product, bind Phase 1 shared contracts to #2, bind the initially read-only Logseq DB adapter to #4, and produce Trama's exact implementation plan before any adapter source is added.

**Files:**
- Create: `docs/superpowers/plans/2026-09-01-logseq-read-contract-and-adapter.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/internal/PERSISTENT_GOAL.md`

**Required decisions:**

- Trama owns graph identification, official Logseq OG/DB adapters, normalized page/subtree acquisition, capability/provenance capture, companion lifecycle, and Nodi-facing UX.
- Plumber owns the consumer-side `GraphSessionReadPort`, domain mapping, agent-facing CLI/MCP behavior, and explicit runtime selection.
- The Phase 1 contract covers graph/session identity, page/subtree DTOs, capabilities, provenance, bounded errors, version negotiation, and privacy-safe evidence.
- The Phase 3 adapter begins read-only. Events, Shadow ingestion, and writes are absent.
- The initial adapter and Plumber consumer path work without Brain. Brain #430 remains a parallel research decision and does not authorize a dependency, entitlement, or connection implementation.
- Trama may expose a later optional Brain connection only through public ports. It never imports Brain-private source, shares caches implicitly, or treats Brain as required for Community read-only value.
- Exact source/test paths and the Trama toolchain are fixed by the new Trama plan; this Plumber plan does not invent them across a repository boundary.
- Matryca Knowledge does not yet index Trama as a managed source. After the Trama planning PR merges, onboard its public documentation through a separate Knowledge-governance change; live Trama source remains authoritative until then.

- [x] Verify Trama `main` and its clean implementation worktree.
- [x] Update architecture and roadmap without claiming a runtime.
- [x] Write the exact Trama contract/adapter implementation plan with TDD steps and short PR boundaries.
- [x] Run Trama's foundation validator and hosted CI.
- [x] Merge this documentation PR before either repository implements the shared contract.

Completion evidence: Trama PR #10 established read-contract authority at
`fc51bdaf256f6dba24a1ff46f89e8cb458011b19`; PR #11 froze
`trama.logseq.read/v1` at `0dbda438859753e68a55c297398d66c00a54cc25`;
PR #12 established the Python-first architecture at
`2ac930b5d7ee8f3a420c8fd334e8ba9631a44974`; and PR #13 added the
qualified synthetic OG contract at
`9905e8a36acb83a17a33b702a5fa620d6bfed185`. These commits do not prove a
Logseq DB host adapter.

---

### Task 3: Freeze Plumber Consumer Evidence Policy

**Repository:** `MarcoPorcellato/matryca-plumber`

**PR scope:** Consumer admission policy and evidence fixtures only; no shared-protocol ownership, copied wire schema, source change, or live adapter.

**Files:**
- Create: `tests/compatibility/logseq_db/consumer-evidence-profile-v1.json`
- Create: `tests/compatibility/logseq_db/fixtures/unverified-db-baseline.json`
- Create: `tests/compatibility/logseq_db/fixtures/rejected-incomplete-subtree.json`
- Create: `tests/compatibility/logseq_db/fixtures/rejected-direct-database.json`
- Create: `tests/test_logseq_db_consumer_evidence.py`
- Create: `docs/quality/LOGSEQ_DB_CAPABILITY_BASELINE_2026-09-05.md`
- Modify: `docs/knowledge/inventory.json`
- Modify generated: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: #491 acceptance criteria, exact anchors above, and Trama's
  `trama.logseq.read/v1` DTO authority at
  `main@9905e8a36acb83a17a33b702a5fa620d6bfed185`.
- Produces: Plumber's versioned consumer evidence policy. This outer profile
  decides whether evidence is admissible; it must reference the Trama contract
  and never duplicate, serialize, or fork its request/result semantics.
- Preserves: Trama ownership of host acquisition, DTO semantics, serialization,
  and DB-native result fixtures. Trama's current consumer remains OG-only and
  must not be widened in this task.
- Keeps two namespaces distinct: Trama runtime outcomes (`success`,
  `unsupported`, `incompatible`, `invalid_request`, `not_found`,
  `authority_failure`, `provenance_failure`) and Plumber evidence
  `qualification_state` values. Neither substitutes for the other.

- [ ] **Step 1: Write failing consumer-policy tests**

Tests must reject:

```python
TRAMA_CONTRACT_REFERENCE = {
    "contract_id": "trama.logseq.read/v1",
    "accepted_contract_major": 1,
}
REQUIRED_CAPABILITIES = {
    "graph.identify",
    "page.read",
    "block.subtree.read.complete",
}
ALLOWED_QUALIFICATION_STATES = {
    "supported",
    "deferred",
    "rejected",
    "unverified",
}
```

The policy must reject an unknown contract major; an unpinned Trama source or
evidence reference; non-read-only scope; graph fallback or graph switching;
mutation, sync, import, or export; direct internal-database access; a foreign or
stale session; missing bounded limits or uncertainty; and any top-level-only or
otherwise incomplete subtree represented as complete.

The profile references the Trama request envelope (`contract_id`, accepted
major, operation, request ID, graph selector, and page/block reference) and
result envelope (`contract_id`, version, operation, request ID, outcome,
payload, graph binding, producer, capabilities, and provenance) without
redeclaring their wire representation. Provenance checks use Trama's exact
fields: `source_mode`, `authority`, `source_reference`, `producer`,
`exercised_capabilities`, and `evidence_digest`.

For a future `qualification_state: "supported"`, require exact selected-host
identity, artifact/build digest, Trama/probe commit, fixture digest, result
evidence digest, all three successful operations, `db_native` provenance, exact
graph binding, complete ordered parentage, and zero forbidden state change.
Transport identity is conditional: require the CLI artifact for CLI evidence,
the SDK version only for SDK evidence, and the MCP server identity only for MCP
stdio evidence. Task 3 itself may create only `unverified` and negative fixtures.

- [ ] **Step 2: Run focused tests and observe failure**

```bash
uv run pytest tests/test_logseq_db_consumer_evidence.py -q
```

Expected: FAIL because the evidence profile and fixtures do not yet exist.

- [ ] **Step 3: Add the minimal consumer evidence profile and fixtures**

Require bounded evidence arrays, explicit `qualification_state`, `scope`,
`source`, `limits`, `uncertainty`, and `direct_database_access: false`. Keep
selected-host hashes and lifecycle observations in this outer evidence profile;
do not add them to `trama.logseq.read/v1`. Treat `result_sha256` as the stored
digest of the Trama `evidence_digest`, not as a second independent truth field.

Create a separate Logseq DB evidence catalog/profile. Do not alter
`tests/compatibility/manifest.json`, whose current authority covers the existing
compatibility corpus.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_logseq_db_consumer_evidence.py -q
```

Expected: PASS.

- [ ] **Step 5: Add baseline report**

Record Trama's synthetic OG qualification as fact. Mark DB-host semantics,
page/subtree parity, graph binding, lifecycle, transport, credential storage,
event ordering, cursor semantics, and conflict semantics `unverified` until
executed. State explicitly that this baseline proves consumer-policy rejection,
not Logseq DB support.

- [ ] **Step 6: Run repository gates and commit**

```bash
make docs-inventory-sync
make docs-inventory-md
make docs-check
/usr/bin/make ci
git add tests/compatibility/logseq_db tests/test_logseq_db_consumer_evidence.py \
  docs/quality/LOGSEQ_DB_CAPABILITY_BASELINE_2026-09-05.md \
  docs/knowledge/inventory.json docs/knowledge/inventory.md
git commit -S -m "test(logseq): freeze DB capability evidence"
```

Stop before push or PR unless separately authorized.

---

### Task 4: Execute Official Host Capability Spike in Matryca Trama

**Repository:** `MarcoPorcellato/matryca-trama`

**PR scope:** Isolated non-production probe and exact evidence through the paths fixed by Task 2's accepted Trama plan. No Plumber runtime import and no user graph.

**Interfaces:**
- Consumes: the Trama Phase 1 contract, Plumber's consumer evidence profile, and a dedicated non-sensitive DB test graph.
- Produces: signed/digested Trama evidence for the exact bundled CLI first, official plugin SDK second if needed, and MCP stdio third if needed.

**Blocking proof:** No production adapter task may start until the spike proves
both (a) stable graph identity across the app-open/app-closed session lifecycle
without switching the current graph and (b) that the selected host operation
returns a complete, ordered descendant tree rather than top-level blocks or a
partial page projection.

- [ ] **Step 1: Pin the executable artifact and upstream identity**

Record the downloaded artifact name and SHA-256, embedded `logseq --version`
revision, release target commit, current tag object, Logseq source and docs
commits, Trama commit, probe commit, fixture digest, platform, and raw-result
digest. A mutable nightly tag is discovery metadata only. Use the CLI bundled
with the selected application artifact; never combine an app with an unrelated
global CLI. If the SDK lane is reached, pin the exact `@logseq/libs` package or
source commit compatible with that build. No ranges or ambient global package.

- [ ] **Step 2: Implement the CLI-first read-only probe**

The probe emits only bounded structural results:

```ts
type RequiredProbeResult = {
  graph: { mode: "db"; binding: string; session: string | null };
  page: { id: string; title: string; properties: unknown };
  subtree: Array<{
    id: string;
    parent_id: string | null;
    order: number;
    content: string;
    properties: unknown;
  }>;
};
```

The committed fixture uses synthetic text only. Raw private graph content never enters Git.

Invoke only documented structured-output commands with an explicit `--graph`
for every graph-bound read. The initial command family is `graph list`, `graph
info`, and `show --page|--uuid|--id` as required to prove the three operations.
Never invoke `graph switch`, `graph create`, `graph remove`, import, export,
backup, sync, login, logout, mutation, arbitrary Datascript query, or direct
SQLite access.

- [ ] **Step 3: Add fail-closed identity, lifecycle, and structure assertions**

Reject OG mode, incomplete child traversal, duplicated IDs, broken parent
references, non-contiguous sibling order, foreign graph identity, unsupported
build, unexpected stderr, unbounded output, timeout, revision mismatch, server
replacement, current-graph change, graph-content fingerprint change, and any
attempt to resolve `db.sqlite`.

- [ ] **Step 4: Prove read-only process behavior with the app closed and open**

Use one disposable synthetic DB graph. Before each probe, record graph identity,
content fingerprint, CLI config fingerprint, and `server list`. Run the same
bounded reads once with the desktop app closed and once with it open. After each
probe, repeat all fingerprints and server inspection. Do not automatically
stop, restart, clean, or replace a server; a revision mismatch or ownership
conflict is a terminal negative result for that artifact.

- [ ] **Step 5: Run static and synthetic probe tests**

Run the exact install, test, and build commands frozen by the accepted Trama implementation plan, then validate the resulting evidence with Plumber's consumer contract.

Expected: all PASS without a real user graph.

- [ ] **Step 6: Run the bounded exact-artifact probe**

Use the dedicated disposable DB graph built from the committed synthetic
fixture. Preserve bounded raw logs outside public source and publish only
sanitized structural evidence. Do not classify a surface `supported` unless
graph identity, page read, complete subtree read, app-open/app-closed parity,
and zero forbidden state change all pass.

- [ ] **Step 7: Escalate transport only when evidence requires it**

Apply this rule:

```text
If the exact bundled CLI proves the full contract and bounded lifecycle:
    select CLI transport.
Else if the official plugin SDK proves the full contract in the companion:
    select plugin SDK transport.
Else if MCP stdio proves the full contract with isolated lifecycle:
    select MCP stdio transport.
Else:
    declare NO-GO; publish capability evidence; implement no adapter.
```

MCP HTTP is not an escalation target while upstream issue #1101 is open. Closed
issues #832 and #833 remain regression inputs, not proof that the selected
artifact is safe.

- [ ] **Step 8: Run gates and commit exact evidence**

Run Trama's exact focused and full gates. Commit the probe and sanitized evidence in Trama; update Plumber's baseline only in a separate short documentation PR pinned to the exact Trama commit and result digest.

Plumber #491 closes only when both exact hosted check sets are green and the capability matrix supports one adapter or records an honest NO-GO.

---

## Decision Gate D1 — Select Transport or Stop

No production branch starts before Tasks 3 and 4 merge.

### Outcome A — Exact bundled CLI qualifies

Create a focused Trama CLI-adapter plan. It must bind executable and application
revision, explicit graph selection, structured decoding, complete subtree
semantics, timeouts, response bounds, stderr, server ownership, revision
mismatch, disconnect, and unavailable-capability errors. It must never change
the current graph or automatically replace a server.

### Outcome B — Plugin SDK qualifies

Continue through Trama #2/#4 and reconcile Plumber #492/#493: shared protocol fixtures, split pairing/security responsibilities, one Trama dual-mode companion shell, then Plumber session routing. Do not create a companion package inside Plumber.

### Outcome C — MCP stdio qualifies

Create a focused per-process stdio adapter plan with exact graph binding,
authentication if required by the selected build, complete subtree semantics,
bounded output, timeout, cancellation, child-process cleanup, and protocol-error
handling. Do not reuse the HTTP server or claim multi-session support.

### Outcome D — No candidate qualifies

Publish the negative result, keep #17 blocked, and do not implement a partial adapter. Re-run #491 only against a newer exact Logseq baseline after upstream capabilities materially change.

---

## Post-D1 Trunk PR Map

These are dependency and outcome boundaries, not authorization to create branches before D1.

| Order | Repository | PR outcome | Tracking | Merge gate |
| ---: | --- | --- | --- | --- |
| 5 | Trama | Implement one versioned graph/session, page, subtree, capability, provenance, error, and bound contract with negative fixtures | Trama #2 | Contract tests PASS; no adapter or transport |
| 6 | Trama + Plumber, separate PRs | Freeze pairing, scopes, revocation, Host/Origin, privacy, and split implementation ownership when companion transport is selected | Trama #2; Plumber #493 | Cross-repository fixtures agree; UI token not reused |
| 7 | Trama | Scaffold the single dual-mode read-only Trama shell and selected official Logseq adapter | Trama #4 | OG/DB mode detection, graph identity, page/subtree acquisition, and content-free health PASS |
| 8 | Plumber | Add transport-neutral `GraphSession` plus session-bound `GraphSessionReadPort`; consume the exact Trama contract and leave filesystem `GraphReadPort` unchanged | Plumber #17/#493 | Existing OG/Shadow parity unchanged |
| 9 | Plumber | Route one DB page read | Plumber #17 | App-visible page parity and fail-closed session tests PASS |
| 10 | Plumber | Route one complete ordered DB subtree read | Plumber #17 | Parentage/order/content/property parity PASS; incomplete result rejected |
| 11 | Trama + Plumber, separate PRs | Publish experimental compatibility guides and one exact-version support matrix | Trama #4; Plumber #490 | Both hosted CI sets and one clean-install qualification PASS |

Each row receives its own detailed implementation plan after D1 fixes transport and exact interfaces. This avoids inventing source paths or APIs before evidence selects them.

## Parallel Clean Architecture Lane: Reduce `get_graph_read_port`

This lane records the approved cleanup without coupling it to Logseq DB
compatibility. It may run before or after the capability spike only when no
integration slice overlaps its files. It never blocks D1 and never adds DB
selection to the filesystem port.

**Current evidence:** `get_graph_read_port` is short but combines Shadow-health
policy, concrete adapter construction, and a discarded root canonicalization.
Its two production callers are `handle_read_subtree` and the installed-wheel
probe. Code-graph orientation reports a CRITICAL transitive blast radius across
20 modules, so signature, fallback, and wheel-probe behavior are frozen until
characterization passes.

### Refactor PR A: Characterize existing selection

**Files:**
- Modify: `tests/test_graph_repository.py`
- Modify only as needed: `tests/test_shadow_read_port.py`
- Modify only as needed: `tests/test_shadow_hardening_axis3_routing.py`
- Modify only as needed: `tests/test_beta_readiness_evidence.py`

- [ ] Prove disabled or unhealthy Shadow returns `MarkdownGraphRepository`.
- [ ] Prove healthy Shadow returns `ShadowGraphRepository` without creating Shadow artifacts.
- [ ] Prove health changes after selection retain query-time fail-closed fallback.
- [ ] Prove `handle_read_subtree` retains current behavior and the wheel evidence schema retains its existing duplicate-fallback contract. Add a narrowly controlled `wheel_probe_main` execution test only if it can remain deterministic and isolated.
- [ ] Run the focused tests, `tests/test_graph_layer_boundary.py`, and full `make check` without changing production source.

### Refactor PR B: Extract one pure selection decision

**Files:**
- Modify: `src/agent/markdown_graph_repository.py`
- Modify: characterization tests from PR A only when required by the unchanged public contract.

- [ ] Run exact-head GitNexus impact before source edits; stop and report if direct callers or affected safety processes changed.
- [ ] Add the smallest private pure selector, such as `_port_for_shadow_readiness(is_ready: bool) -> GraphReadPort`.
- [ ] Keep `get_graph_read_port(graph_root: Path | None = None) -> GraphReadPort` as the compatibility façade that computes readiness and delegates.
- [ ] Retain the `resolved_graph_root` call by default. Remove it only under a dedicated test that proves exact exception and call-order compatibility; PR A's general characterization alone is insufficient.
- [ ] Do not add a factory hierarchy, configuration object, DB condition, session type, transport, event behavior, or write behavior.
- [ ] Run focused tests, `tests/test_graph_layer_boundary.py`, full `make check`, GitNexus `detect_changes()` against `main`, and a second exact-candidate impact review.

Moving the selector to another module is default NO-GO unless the two-PR result
proves a concrete ownership or dependency-direction defect. A file move alone
would add abstraction without reducing responsibility.

## Initial Compatibility Exit Gate

The programme may claim **experimental Logseq DB read-only compatibility** only when all conditions hold:

- graph identity and DB mode bind to one active session;
- one page read matches app-visible title, ID, and supported typed properties;
- one complete subtree read matches app-visible IDs, parentage, sibling order, content, and supported properties;
- graph switch, disconnect, stale session, unsupported version, missing capability, foreign binding, malformed response, and incomplete subtree fail explicitly;
- no code accesses Logseq internal SQLite;
- no DB graph silently falls back to Markdown;
- existing OG, Shadow, Strict Read Only, MCP, and CLI regression suites pass;
- exact Logseq build, adapter version, fixtures, and evidence digest are public;
- README and operator docs label support experimental and state exclusions.

## Deferred Programmes and Re-entry Gates

### Events and convergence — DEFERRED

Re-enter only after initial read compatibility passes. New plan must cover cursor semantics, deduplication, reordering, gaps, reconnect, graph-switch invalidation, and bounded resynchronization. No event claim from method-name inspection alone.

### DB-source Shadow acceleration — DEFERRED

Re-enter only after snapshot and event semantics are qualified. New design must define DB-source generation, freshness, rebuild, reconciliation, source identity, and explicit fallback. Existing Markdown Shadow evidence does not qualify DB-source ingestion.

### Host-authoritative DB writes — DEFERRED

Remain under #25. Re-enter only after official expected-revision or equivalent atomic conflict semantics, idempotency, timeout reconciliation, app validation, and undo/redo are reproducibly proven. If atomic conflict rejection cannot be proven, Matryca remains read-only.

### Optional Matryca Brain connection — DEFERRED, NON-BLOCKING

[Brain #430](https://github.com/MarcoPorcellato/Matryca-per-Delineat/issues/430) and Trama ADR-0002 require strict product and repository separation. The initial Logseq DB compatibility programme neither waits for nor implements “Connect to Matryca Brain.” Re-enter only after Trama and Plumber have compatible released read contracts and a separate accepted design defines:

- public versioned Trama and Brain ports without Brain-private source imports;
- explicit authentication, least-authority capabilities, graph selection, consent, revocation, and disconnection;
- mode-correct source authority: OG Markdown versus the official Logseq DB host;
- bounded data flow, privacy-safe provenance, independent caches, and no silent replication;
- version-skew rejection, failure recovery, licensing and entitlement boundaries, and non-destructive downgrade;
- contract tests against exact supported Trama, Plumber, and Brain releases.

Brain may later become an optional destination for selected graphs or derived views. It is not required for Trama Community, the companion runtime, or Plumber's initial DB reads.

### Tine coexistence — PARALLEL, NON-BLOCKING

Tine Discussion #334 establishes that Direct Files already supplies the basic read-only coexistence model and that Matryca-side mutation while Tine is closed needs no new Tine protocol. Plumber therefore adds no Tine-specific adapter.

Tine #337 closed as completed on 2026-08-27 after the Concord/external-file synchronization work. The current qualification target is `v0.6.98` in Direct Files mode. Closure is upstream evidence, not proof of arbitrary two-writer safety:

- keep Matryca Strict Read Only whenever Tine may be active;
- run only a small versioned reader/no-write corpus under Plumber #494;
- do not attach a generic proposal to closed #337; reopen or create a focused Tine issue only after an exact current-version failure is reproduced;
- make no concurrent-write claim;
- treat open Tine #108 and #109 as possible future host-authoritative CLI/MCP surfaces only after their revision, locking, conflict, and atomic-save contracts are executable;
- treat Tine #33 as Git/sync integration, not as a graph mutation authority.

This lane does not share Logseq DB adapter code. Shared outputs are compatibility vocabulary, fixtures where licensing permits, and public evidence style only.

## Cost-Aware Delegation

- Use deterministic source/API queries before model analysis.
- Delegate bounded source inventories, fixture review, documentation checks, and test-output distillation to lower-cost workers.
- Keep transport selection, security, graph identity, data-integrity claims, final diff review, and merge decisions with the primary maintainer workflow.
- One worker owns one disjoint file group; overlapping edits are serialized.
- Stop a delegated attempt after one failure and one focused correction.

## Restart and Handoff Contract

The compact restart-safe execution pointer is
[`docs/quality/LOGSEQ_DB_READ_ONLY_COMPATIBILITY_PERSISTENT_GOAL_2026-09-05.md`](../../quality/LOGSEQ_DB_READ_ONLY_COMPATIBILITY_PERSISTENT_GOAL_2026-09-05.md).
This plan remains the only milestone and completion authority; the persistent
goal must never redefine its scope or gates.

At every PR boundary record:

- repository and worktree absolute path;
- branch, exact HEAD, verified base, and dirty state;
- issue and PR number;
- focused and full checks with exact commit;
- upstream Logseq, SDK, fixture, and evidence hashes when applicable;
- unproven gates and next dependency;
- explicit statement that events, Shadow acceleration, and writes remain deferred.

Temporary worktree paths are not durable evidence. Preserve approved work in a local commit; push only under explicit authorization.

## Completion Checklist

- [x] Historical primary recovery preserved prior work; current delivery worktree starts clean from verified GitHub `main`.
- [x] Task 1 plan/current-anchor PR is merged.
- [x] Trama is publicly named as the only companion product; no second companion is created in Plumber.
- [x] Trama Phase 1 contract execution authority and `trama.logseq.read/v1` are merged under Trama #2.
- [x] Trama Python-first foundation and synthetic OG contract qualification are merged without a DB-host claim.
- [ ] Plumber's consumer evidence policy is merged without copying Trama's contract schema.
- [ ] Trama's capability probe and Plumber #491 reach supported adapter selection or a public NO-GO.
- [ ] D1 transport decision is recorded.
- [ ] Contract and security PRs appropriate to selected transport are merged.
- [ ] Graph/session identification works fail-closed.
- [ ] Page read parity passes.
- [ ] Complete subtree parity passes.
- [ ] Existing OG and Shadow regressions pass.
- [ ] Public experimental support matrix names exact supported versions and limitations.
- [ ] Events remain unclaimed and separately tracked.
- [ ] DB-source Shadow acceleration remains unclaimed and separately tracked.
- [ ] DB writes remain unclaimed and separately tracked under #25.
- [ ] Tine coexistence remains read-only, version-bound, non-blocking, and separate from the Logseq DB adapter.
- [ ] Matryca Brain remains optional, separately released, and outside the initial read path; any future connection remains tracked under Brain #430.
- [ ] `get_graph_read_port` characterization is merged in a separate PR without production changes.
- [ ] Any approved `get_graph_read_port` reduction preserves its signature, filesystem-only ownership, Shadow fallback, and wheel-probe behavior.
