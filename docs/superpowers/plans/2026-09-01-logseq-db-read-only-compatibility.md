# Logseq DB Read-Only Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an evidence-backed experimental Logseq DB read path for graph identification, one page read, and one complete block-subtree read, using Matryca Trama as the named companion and adapter product while preserving Matryca Plumber's existing Logseq OG, Shadow DB, Strict Read Only, MCP, and CLI behavior.

**Architecture:** A pinned capability spike in Matryca Trama selects one supported Logseq host surface before production code is written. Trama owns the user-facing companion, official Logseq OG/DB adapters, and host-object normalization into a small versioned shared contract. Matryca Plumber consumes that contract through a new session-bound `GraphSessionReadPort`; its existing filesystem `GraphReadPort` remains the OG/Shadow contract. Matryca Brain remains an optional future destination behind separate public ports and is not a dependency of this read path. Events, DB-source Shadow acceleration, all DB writes, and Trama–Brain connection remain separate gated programmes.

**Tech Stack:** Matryca Trama's TypeScript/Logseq adapter surface, Python 3.12+, pytest, Pydantic-free Plumber boundaries, official Logseq JS Plugin SDK and/or built-in MCP/CLI probes, JSON fixtures, GitHub Actions, Matryca documentation profile v1.0 over OKF v0.2.

**Spec:** [`docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md`](../../roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md)

## Global Constraints

- Start from public `main@3208bedfaeef0708034089057702cd21fa5dec52`; revalidate GitHub `main` before every branch.
- Use short-lived branches from current `main`; every PR targets `main`, carries one reviewable concern, and merges before a dependent branch is cut.
- Never commit directly to `main` and never use a long-lived integration branch.
- Never open, query, copy, export as an implementation shortcut, or mutate Logseq internal `db.sqlite`.
- Use only a pinned and reproduced official Logseq plugin SDK, built-in MCP, CLI, or other supported host surface.
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

## Verified Current Anchors — 2026-09-01

| Surface | Exact anchor | Meaning |
| --- | --- | --- |
| Matryca Plumber public main | `3208bedfaeef0708034089057702cd21fa5dec52` | Current planning base |
| Matryca Trama public main | `cd9ec408ed9d4ece39d3eeaef506f4b172ab77d5` | Named companion; document-first foundation, no runtime claim |
| Trama shared contracts | [#2](https://github.com/MarcoPorcellato/matryca-trama/issues/2) | Versioned Parser/Plumber contract track |
| Trama Logseq adapters | [#4](https://github.com/MarcoPorcellato/matryca-trama/issues/4) | OG and initially read-only DB adapter track |
| Matryca Brain public main | `e69a97a8c702a773c9a3ce8307b5a667ed2be1dd` | Current verified Brain source observation; no dependency is introduced |
| Trama–Brain product boundary | [Brain #430](https://github.com/MarcoPorcellato/Matryca-per-Delineat/issues/430), [Trama ADR-0002](https://github.com/MarcoPorcellato/matryca-trama/blob/main/docs/decisions/ADR-0002-TRAMA_BRAIN_PRODUCT_BOUNDARY.md) | Separate products and repositories; optional future public contract |
| Existing strategy | `docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md` | Design authority |
| Logseq documentation | `08f855f24d66e4509b7ea808554c13b4649e6ee1` | Current DB and MCP documentation reviewed for this plan |
| Logseq `test/db` | `5a23230a56832a6aab4a556d9894955120d26ece` | Stable-beta source candidate for probes |
| Logseq nightly target | `dde0aba2d441c962d28989b0af894cc261da3898` | Nightly published 2026-08-26 |
| Parser source in Matryca Knowledge | `e374014bf3787d3ba64d1f3284d8e11db316d437` | Current ecosystem source anchor; runtime remains pinned by this repository |
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
- Official built-in MCP currently documents top-level block operations but not complete child-block operations or general property-value coverage. It therefore cannot be assumed to satisfy Matryca's complete subtree contract.

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

## Local Main Recovery Before Implementation — COMPLETE

The current primary checkout is not safe for new work: local `main@701b923d567baa04e89846d973b7828a48fc1b30` is ahead 19, behind 19, has two modified tracked files, and contains an untracked `.worktrees/` directory. The commit is already retained by local branch `feat/pocket-alpha1a-contracts`, but the uncommitted bytes still require preservation.

This recovery is a local operator step, not a product PR:

- [x] Recorded complete primary-checkout status, branch refs, worktree registrations, and the two dirty diffs.
- [x] Created `recovery/main-dirty-20260901-701b923` from the divergent local `main`.
- [x] Preserved only the two tracked modified files in signed commit `b036d3bdc6c289b3eff37a058fafb1c9d8dec24a`; signature verification passed.
- [x] Verified `.worktrees/human-governed-adaptive-retrieval-plan-20260816` is registered and added only `.worktrees/` to local `.git/info/exclude`.
- [x] Moved local `main` to freshly verified `origin/main@3208bedfaeef0708034089057702cd21fa5dec52`.
- [x] Confirmed local `main` is byte-clean and equals GitHub `main`.
- [ ] Preserve the recovery branch until its owner confirms the two recovered changes have been integrated or abandoned.

Do not use `git reset --hard`, `git clean`, stash, or worktree deletion for this recovery.

---

### Task 1: Publish Current Programme Anchors

**PR scope:** Documentation only. Update the accepted strategy with current upstream pins, the confirmed read-only target, the trunk-based sequence, and this plan link.

**Files:**
- Create: `docs/superpowers/plans/2026-09-01-logseq-db-read-only-compatibility.md`
- Modify: `docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md`
- Modify generated: `docs/knowledge/inventory.json`
- Modify generated: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: existing strategy and verified public/upstream anchors.
- Produces: one public execution authority linking Plumber #490/#491/#492/#493/#17/#25 with Trama #2/#4 and the non-blocking Tine lane.

- [ ] **Step 1: Add a dated current-state addendum to the strategy**

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

- [ ] **Step 2: Add exact upstream anchors and drift rule**

Require every executable probe to record Logseq source, SDK/package lock, documentation commit, app build, Trama commit, Plumber commit, graph fixture digest, probe source commit, and raw-result digest. A later upstream version requires a new evidence row; it must not overwrite the old row. Tine qualification additionally records exact release, source commit, Direct Files mode, platform, and proof of zero Matryca graph writes.

- [ ] **Step 3: Link this plan from the strategy**

The strategy remains design authority; this file owns execution order and PR boundaries.

- [ ] **Step 4: Regenerate documentation inventory**

Run:

```bash
make docs-inventory-sync
make docs-inventory-md
```

Expected: the new plan has one curated inventory entry and generated Markdown matches JSON.

- [ ] **Step 5: Run documentation gates**

Run:

```bash
make docs-check
make docs-audit
```

Expected: `docs-check` PASS; `docs-audit` completes as informational evidence.

- [ ] **Step 6: Commit the documentation slice**

```bash
git add docs/roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md \
  docs/superpowers/plans/2026-09-01-logseq-db-read-only-compatibility.md \
  docs/knowledge/inventory.json docs/knowledge/inventory.md
git commit -S -m "docs(logseq): plan DB read-only compatibility"
```

Stop before push or PR unless separately authorized.

---

### Task 2: Establish Matryca Trama Execution Authority

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

- [ ] Verify Trama `main` and its clean implementation worktree.
- [ ] Update architecture and roadmap without claiming a runtime.
- [ ] Write the exact Trama contract/adapter implementation plan with TDD steps and short PR boundaries.
- [ ] Run Trama's foundation validator and hosted CI.
- [ ] Merge this documentation PR before either repository implements the shared contract.

---

### Task 3: Freeze Plumber Consumer Capability Evidence Schema

**Repository:** `MarcoPorcellato/matryca-plumber`

**PR scope:** Consumer acceptance and evidence contract only; no shared-protocol ownership and no live adapter.

**Files:**
- Create: `tests/compatibility/logseq_db/capability-schema-v1.json`
- Create: `tests/compatibility/logseq_db/fixtures/supported-minimal.json`
- Create: `tests/compatibility/logseq_db/fixtures/rejected-incomplete-subtree.json`
- Create: `tests/compatibility/logseq_db/fixtures/rejected-direct-database.json`
- Create: `tests/test_logseq_db_capability_contract.py`
- Create: `docs/quality/LOGSEQ_DB_CAPABILITY_BASELINE_2026-09-01.md`
- Modify: `docs/knowledge/inventory.json`
- Modify generated: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: #491 acceptance criteria, exact anchors above, and the accepted Trama Phase 1 contract plan.
- Produces: Plumber's `logseq-db-capability/v1` consumer evidence profile. It must validate the shared Trama contract rather than fork it.

- [ ] **Step 1: Write failing schema-contract tests**

Tests must reject missing values for:

```python
REQUIRED_IDENTITY = {
    "logseq_source_commit",
    "logseq_build_id",
    "documentation_commit",
    "sdk_version",
    "probe_commit",
    "fixture_sha256",
    "result_sha256",
}
REQUIRED_CAPABILITIES = {
    "graph.identify",
    "page.read",
    "block.subtree.read.complete",
}
ALLOWED_STATUS = {"supported", "read-only", "deferred", "rejected", "unverified"}
```

Also reject a capability result that reports direct internal-database access or calls a top-level-only block result complete.

- [ ] **Step 2: Run focused tests and observe failure**

```bash
uv run pytest tests/test_logseq_db_capability_contract.py -q
```

Expected: FAIL because schema and fixtures do not yet exist.

- [ ] **Step 3: Add minimal JSON Schema and fixtures**

Require bounded evidence arrays, explicit `status`, `source`, `limits`, and `uncertainty`, plus `direct_database_access: false`.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_logseq_db_capability_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Add baseline report**

Record only documentation-confirmed capabilities as facts. Mark page/subtree parity, graph binding, plugin origin, credential storage, event ordering, cursor semantics, and conflict semantics `unverified` until executed.

- [ ] **Step 6: Run repository gates and commit**

```bash
make docs-inventory-sync
make docs-inventory-md
make docs-check
/usr/bin/make ci
git add tests/compatibility/logseq_db tests/test_logseq_db_capability_contract.py \
  docs/quality/LOGSEQ_DB_CAPABILITY_BASELINE_2026-09-01.md \
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
- Produces: signed/digested Trama evidence for official plugin SDK, built-in MCP, and CLI surfaces where callable.

**Blocking proof:** No production adapter task may start until the spike proves both (a) stable graph identity across the session and graph-switch lifecycle and (b) that the selected host operation returns a complete, ordered descendant tree rather than top-level blocks or a partial page projection.

- [ ] **Step 1: Pin all JavaScript dependencies and upstream identity**

Use an exact `@logseq/libs` version or exact Git commit resolved from the tested Logseq build. No ranges, ambient global package dependency, or probe source inside Plumber.

- [ ] **Step 2: Implement three read-only probes**

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

- [ ] **Step 3: Add fail-closed probe assertions**

Reject OG mode, incomplete child traversal, duplicated IDs, broken parent references, non-contiguous sibling order, foreign graph identity, unsupported build, and any attempt to resolve `db.sqlite`.

- [ ] **Step 4: Run static and synthetic probe tests**

Run the exact install, test, and build commands frozen by the accepted Trama implementation plan, then validate the resulting evidence with Plumber's consumer contract.

Expected: all PASS without a real user graph.

- [ ] **Step 5: Run bounded real-app probe once per selected official surface**

Use a dedicated disposable DB graph built from the committed synthetic fixture. Preserve exact app build, SDK/package lock, command, result digest, and negative outcomes. Do not classify a surface `supported` unless graph identity, page read, and complete subtree read all pass.

- [ ] **Step 6: Make adapter decision**

Apply this rule:

```text
If built-in MCP proves complete subtree and graph/session binding:
    select built-in MCP as primary transport.
Else if official plugin SDK proves them:
    select companion SDK transport.
Else:
    declare NO-GO; publish capability evidence; implement no adapter.
```

- [ ] **Step 7: Run gates and commit exact evidence**

Run Trama's exact focused and full gates. Commit the probe and sanitized evidence in Trama; update Plumber's baseline only in a separate short documentation PR pinned to the exact Trama commit and result digest.

Plumber #491 closes only when both exact hosted check sets are green and the capability matrix supports one adapter or records an honest NO-GO.

---

## Decision Gate D1 — Select Transport or Stop

No production branch starts before Tasks 3 and 4 merge.

### Outcome A — Built-in MCP qualifies

Create a focused follow-up implementation plan for an authenticated streamable-HTTP adapter. The plan must bind token audience, graph selection, complete subtree semantics, response bounds, and unavailable-capability errors. Matryca Trama remains the named companion product, but a Trama-specific transport must not be required when the built-in MCP already satisfies the read contract.

### Outcome B — Plugin SDK qualifies

Continue through Trama #2/#4 and reconcile Plumber #492/#493: shared protocol fixtures, split pairing/security responsibilities, one Trama dual-mode companion shell, then Plumber session routing. Do not create a companion package inside Plumber.

### Outcome C — Neither qualifies

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

- [x] Primary `main` is clean and matches GitHub `main` without losing prior work.
- [ ] Task 1 plan/current-anchor PR is merged.
- [ ] Trama is publicly named as the only companion product; Plumber #492 is reconciled without creating a second companion.
- [ ] Trama Phase 1 contract execution authority is merged under Trama #2.
- [ ] Plumber's consumer capability evidence schema is merged.
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
