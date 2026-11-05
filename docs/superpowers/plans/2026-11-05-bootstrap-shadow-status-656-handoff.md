# Issue #656: Bootstrap and Shadow status handoff

Status: reviewed proposal; implementation and runtime qualification have not started. The next decision is approval of the implementation scope below. This document records the proposal and does not grant execution or publication permission.

## Starting point

- Repository: [MarcoPorcellato/matryca-plumber](https://github.com/MarcoPorcellato/matryca-plumber).
- Verified planning base: [`2c0b56db90fd9613ab80e51bdad1edca949cf22a`](https://github.com/MarcoPorcellato/matryca-plumber/commit/2c0b56db90fd9613ab80e51bdad1edca949cf22a), tree `890c8bd8cef2e8d2338646830a5f3c1d5d75051b`. Recheck main, the issue and competing changes before implementation.
- [#656](https://github.com/MarcoPorcellato/matryca-plumber/issues/656) stays open. The exact software closure of the reported deployment is not established.
- [#659](https://github.com/MarcoPorcellato/matryca-plumber/pull/659) already clarifies Strict Read Only guidance. [#663](https://github.com/MarcoPorcellato/matryca-plumber/pull/663) separately bounds Linux/macOS dashboard execution to 1800 seconds plus one five-second cleanup deadline. Windows remains unchanged. Neither change proves production dashboard performance.
- The retained 1,115-page synthetic dashboard attempt failed to complete within the former 120-second ceiling in the `refs` phase, with verified cleanup. It was not repeated at 1800 seconds. Do not infer a root cause from the phase marker.

## Why both statuses can be true

`collect_bootstrap_status()` in `src/graph/bootstrap_status.py` reports the graph-local Master Index/catalog and daemon checkpoint. If the checkpoint is missing, the legacy progress values are 0/0 and the recovery source is `missing`. A missing catalog keeps the Soft Gate active.

`resolve_shadow_db_state_for_api()` in `src/shadow/state_api.py` reports readiness of a separate, external derived cache. A ready cache can coexist with a missing graph-local catalog and checkpoint. Conversely, a complete catalog does not require a ready cache. Neither response authorizes writes or uncatalogued discovery.

The remaining problem is machine-readable ambiguity, not a requirement for equal counts. Documentation alone already explains the distinction; combining endpoints, copying counters or declaring a common readiness result would change semantics and can imply permissions the caller does not have.

## Proposed contract

Keep the collector, snapshot constructor, existing `to_dict()` keys and values, checkpoint defaults and Soft Gate formula unchanged. Add exactly four explanatory fields to the bootstrap JSON projection:

| Field | Value |
| --- | --- |
| `status_scope` | `graph_local_catalog` |
| `bootstrap_progress_source` | `graph_local_daemon_checkpoint`; existing `checkpoint_recovery_source` still qualifies the origin of legacy values |
| `catalog_gate_reasons` | Ordered list of the fixed reason codes below |
| `catalog_bootstrap_action` | `not_required`, `not_permitted_read_only`, or `requires_explicit_authorization` |

Derive the reasons from the existing snapshot, in this order:

1. If the Master Index is absent, add `master_index_missing`. Otherwise, if the catalog is incomplete, add `catalog_stale` when the existing stale flag is true, or `catalog_incomplete` otherwise.
2. Add `bootstrap_failed` when the existing failure flag is true.
3. Add `phase1_in_progress` when the existing progress flag is true.

A missing checkpoint is not itself a blocker. In particular, a complete catalog without a checkpoint must stay complete. A failed checkpoint with partial counters does not count as active progress under the existing collector. Simultaneous failure/progress flags may be used only in explicitly constructed helper tests, not manufactured by changing the collector.

The action is `not_required` when the gate is inactive, `not_permitted_read_only` when active in Strict Read Only, and `requires_explicit_authorization` otherwise. It describes catalog bootstrap policy only; it is not a repair instruction, a permission grant or a filesystem capability probe.

Use typed, pure private helpers in `src/graph/bootstrap_status.py` and serialize reasons as a JSON list. No additional reads, scans, cache probes, initialization, repair, background work or cross-layer imports. Only the new explanatory fields are content-free; the existing payload includes graph identity/path and failure detail. Leave `shadow_status` unchanged, including its profile, counts, reason codes and fallback behavior. Separate reads are not an atomic combined snapshot.

## Implementation scope: fourteen paths

1. `src/graph/bootstrap_status.py` — additive projection, finite reason/action types and explanatory formatting.
2. `tests/test_bootstrap_status.py` — legacy compatibility, truth table and synthetic read-only controls.
3. `src/agent/mcp_server.py` — bootstrap/search status documentation strings only.
4. `tests/test_mcp_server.py` — tool metadata checks.
5. `docs/openspec/agent/soft-gate.md` — policy and field definitions.
6. `docs/openspec/agent/mcp-tools.md` — bootstrap contract summary.
7. `docs/openspec/agent/tool-reference.md` — independent examples.
8. `docs/openspec/agent-onboarding.md` — explain sources and policy.
9. `llms.txt` — concise contract guidance.
10. `.well-known/llms.txt` — byte-identical mirror.
11. `SYSTEM_PROMPT.md` — generated from the fragments.
12. `CHANGELOG.md` — one Unreleased entry when the runtime change is implemented.
13. `docs/knowledge/inventory.json` — only if required by the documentation generator.
14. `docs/knowledge/inventory.md` — only the required generated view update.

Keep the daemon checkpoint reader, catalog loader, read handlers, Shadow implementation, frontend, `/api/state`, configuration, dependencies, version and release artifacts outside this change. No Parser release prerequisite for this slice. Report scope expansion or strict-client incompatibility rather than silently changing existing policy. Treat public-contract impact as high; verify current impact and consumers before editing.

## Characterization and acceptance

1. Freeze explicit expected legacy dictionaries before production edits: missing, complete, stale, failed, progressing and checkpoint backup/reset cases. In each assertion remove only the four additions and compare every remaining key/value with the fixed expectation. Do not derive expected legacy values from the changed implementation.
2. Pin reason ordering and action under both policy modes. Cover missing-index precedence, failed partial counters without progress, complete catalog without a checkpoint, and preserved invalid-policy-token failure.
3. Extend `test_read_only_catalog_status_does_not_confuse_ready_external_shadow` with exact new fields. Add complete catalog with non-ready Shadow. Provision a tiny disposable synthetic graph and external cache before observations. Forbid Shadow probes, cache initialization and AST parsing in the bootstrap call. Preserve legacy checkpoint/catalog decoding and completeness inspection; the new fields add no parsing. Missing Shadow cache must not be created by status; preserve durable database state and do not claim byte immutability of arbitrary operating-system bookkeeping.
4. Exercise checkpoint and catalog corruption using fresh fixture roots or clearing only fixture-owned catalog caches. Include a Master Index to reach catalog loading; test its absent-index short circuit separately. Assert unchanged Strict Read Only graph inventory, bytes and relevant metadata (excluding atime). Characterize existing writable-mode restoration, quarantine and backup refresh separately; do not assert whole-call purity there.
5. Verify focused RED for missing additions, not an import or environment failure. Implement the pure projection; require GREEN with unchanged legacy values and no new side effects. Run bootstrap, MCP metadata, Shadow state/reason, read-only daemon, daemon checkpoint, graph-layer and prompt builder regressions using existing synthetic fixtures and a verified test environment. No personal graph or new scale run.
6. Update the named documentation, regenerate the system prompt, verify its hash and both quickstarts, and run repository documentation, format, lint, typing and source-safety checks. Keep generated changes scoped. Use the normal hosted CI after separately approved integration; no new execution controller, heavy local preflight, or package build is needed for this slice.
7. Obtain independent review of the frozen implementation candidate. Stop on scope drift, changed permissions or legacy values, unexpected failures, or uncertain cleanup. Record actual evidence separately from expected results.

## Resume and stop points

Start by verifying the latest main and issue, reviewing this scope and identifying any competing changes. Obtain maintainer approval for implementation, synthetic tests and independent review. Then work in an isolated branch. Commit, push, PR, merge, releases and changes to issue state require applicable separate authority. Reference #656 without auto-closing it.

Keep the independent performance lane separate: [Parser #267](https://github.com/MarcoPorcellato/logseq-matryca-parser/pull/267) addresses ownership lookup work in source, not end-to-end dashboard qualification. Before any adoption, verify the exact published Parser artifact and provenance; plan the coordinated lock, runtime profile and verifier update while preserving the original alpha.3 tuple. A lock-only upgrade, unpublished dependency or rerun of the consumed scale attempt is not part of this handoff.

No implementation or runtime test is represented as complete by this handoff.
