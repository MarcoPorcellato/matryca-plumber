# v2.0.0-beta.1 readiness — decision record

## Problem Description

`v2.0.0-beta.1` / PyPI `2.0.0b1` is the first public beta of the opt-in Shadow DB read cache. It supersedes the `v2.0.0-alpha.5` hardening baseline for new prerelease installs. The feature remains default-off and must not be described as default-on; re-qualification against the released source is required before that separate decision.

Supporting experiment results are summarized in [`V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md`](../V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md). That sanitized ledger is not a gate-completion record: the checklist in this file remains the local source of truth for the beta decision. The post-[#317](https://github.com/MarcoPorcellato/matryca-plumber/pull/317) r4 installed-wheel gate is current; r3 remains historical only.

The beta scope is limited to the existing Shadow read path: bootstrap and reconciliation, FTS5 BM25, recursive CTE subtree reads, health-gated routing, and their Markdown/BM25 fallbacks. Logseq Markdown remains the system of record. Biological memory and Logseq DB Safe-Sync are Phase 4 work and are excluded from beta. `MATRYCA_SHADOW_DB_ENABLED` remains opt-in and default-off.

The product's `MATRYCA_PAGE_PARSE_TIMEOUT_S` default remains **15 seconds**. A timeout must make health non-ready and route reads to the established Markdown/BM25 fallback. The private beta-evidence `wheel` and `soak` commands require an explicit bounded deadline (2–120 seconds) for their child probes; **60 seconds** is allowed for evidence collection only and does not demonstrate readiness at the 15-second product default.

## Proposed Architectural Solution

Use this record as the release decision gate for `v2.0.0-beta.1`. A gate is complete only when its evidence is sanitized and reproducible; a green unit test alone does not replace an installed-wheel or real-vault check.

| Gate | Required evidence | Status |
|------|-------------------|--------|
| Bounded parser containment | [#297](https://github.com/MarcoPorcellato/matryca-plumber/issues/297) is merged; a timed-out or failed page parse cannot publish a partial AST cache or Shadow generation; the last good incremental page remains usable; health becomes non-ready and routing falls back; diagnostics expose only bounded metadata | [x] — #297 is closed and merged; the contracts are covered by `tests/test_bounded_page_parse.py`, which is green. A worker whose parent dies without cleanup is now reaped rather than orphaned, closing the last known containment leak |
| Defect threshold | No open P0/P1 defect in beta scope; every remaining P2 has an explicit disposition | [x] — `PASS`. All 46 open issues were reviewed and classified by the maintainer; none carries a `bug` label. Exactly one falls inside beta scope: the pickle boundary in the bounded page parser, recorded as an open P2 with disposition `deferred` because the fix changes both IPC paths and would invalidate the completed soak. No in-scope P0/P1 exists. The severity and disposition inputs are private operator inputs and are not stored in this repository |
| Sanitized real-vault soak | At least 24 hours, preferably 3–7 days: flag-off/on cycles, restarts, watcher create/edit/rename/delete convergence, controlled recovery, and unchanged Markdown fingerprints outside explicit fixture changes | [x] — `PASS`, `beta_qualified: true`, 2026-07-28. 144 cycles, 288 attempts, 86 465 s of accumulated exercise at the 15 s product default. Record, including two interruptions and the checks showing they did not affect the result: [`SHADOW_DB_SOAK_24H_EVIDENCE_2026-07-28.md`](../SHADOW_DB_SOAK_24H_EVIDENCE_2026-07-28.md). Not yet the preferred 3–7 days |
| Installed-wheel upgrade and recovery | `2.0.0a5` → `2.0.0b1` on a copied vault; compatible generation/meta preserved; schema mismatch and injected rebuild failure recover safely without partial reads or Markdown writes; wheel identity is reproducibly built and bound to the subsequent soak | [x] — `PASS` after the reproducibility remediation. The binding digest `6fa52103489a5c37…` recorded by this gate is the digest the soak recorded, so the artifact that passed here is the artifact that was soaked |
| Final release evidence | Full CI passes, final code audit matches the intended scope, and the candidate wheel is built and smoke-tested outside the checkout | [x] — with an **explicit, accepted deviation**. Full CI passes on the released tree. The wheel and soak gates bound digest `cf627f3638ae95bb…`, built from an earlier state of the branch; the released source additionally carries per-page quarantine, the orphaned-worker fix, and the config-page permission fix. Those gates therefore evidence the design and the read path, not the published bytes. Accepted because the feature is opt-in, default-off, and fails safe. **This deviation does not carry forward:** re-qualification against the released source is a precondition for default-on, and the record must not be cited as byte-level evidence for the published artifact |

## Estimated Impact

The beta does not change the default read path, vault write authority, or Phase 4 scope. Operators who leave `MATRYCA_SHADOW_DB_ENABLED` unset or false retain the established Markdown and generational-BM25 behavior. Operators who opt in receive Shadow reads only while health is `ready`; otherwise fallback remains mandatory.

The previous r4 observation remains sanitized historical behavior evidence. The later bound wheel/soak result recorded above closes the beta publication gate after the reproducibility remediation. See [`BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md`](../BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md) for the historical root-cause record and rerun protocol.

## Files Involved

- `src/graph/bounded_page_parse.py` and `src/graph/ast_cache.py` — bounded AST parsing and cache publication
- `src/shadow/bootstrap.py`, `src/shadow/sync.py`, and `src/shadow/health.py` — Shadow recovery, health, and fallback
- `tests/test_ast_cache_bounded_parse.py` and `tests/test_shadow_bounded_parse.py` — containment contract
- `docs/roadmaps/ROADMAP_V2_PREPARATION.md` and `docs/roadmaps/ROADMAP_V2_SHADOW_DB.md` — public scope and rollout status

---

**Epic link:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)
_Closed by the v2.0.0-beta.1 publication with all gates above complete and the accepted evidence boundary recorded._
