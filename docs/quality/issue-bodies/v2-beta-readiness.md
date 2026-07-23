# v2.0.0-beta.1 readiness — tracking issue

## Problem Description

`v2.0.0-alpha.5` / PyPI `2.0.0a5` is the published hardening baseline for the opt-in Shadow DB read cache. `v2.0.0-beta.1` is a **candidate only**, not a released version. It must not be tagged, published, or described as default-on until the gates below have evidence from the release candidate.

Supporting experiment results are summarized in [`V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md`](../V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md). That sanitized ledger is not a gate-completion record: the checklist in this file remains the local source of truth for the beta decision. The post-[#317](https://github.com/MarcoPorcellato/matryca-plumber/pull/317) r4 installed-wheel gate is current; r3 remains historical only.

The beta scope is limited to the existing Shadow read path: bootstrap and reconciliation, FTS5 BM25, recursive CTE subtree reads, health-gated routing, and their Markdown/BM25 fallbacks. Logseq Markdown remains the system of record. Biological memory and Logseq DB Safe-Sync are Phase 4 work and are excluded from beta. `MATRYCA_SHADOW_DB_ENABLED` remains opt-in and default-off.

The product's `MATRYCA_PAGE_PARSE_TIMEOUT_S` default remains **15 seconds**. A timeout must make health non-ready and route reads to the established Markdown/BM25 fallback. The private beta-evidence `wheel` and `soak` commands require an explicit bounded deadline (2–120 seconds) for their child probes; **60 seconds** is allowed for evidence collection only and does not demonstrate readiness at the 15-second product default.

## Proposed Architectural Solution

Use this record as the release decision gate for `v2.0.0-beta.1`. A gate is complete only when its evidence is sanitized and reproducible; a green unit test alone does not replace an installed-wheel or real-vault check.

| Gate | Required evidence | Status |
|------|-------------------|--------|
| Bounded parser containment | [#297](https://github.com/MarcoPorcellato/matryca-plumber/issues/297) is merged; a timed-out or failed page parse cannot publish a partial AST cache or Shadow generation; the last good incremental page remains usable; health becomes non-ready and routing falls back; diagnostics expose only bounded metadata | [ ] |
| Defect threshold | No open P0/P1 defect in beta scope; every remaining P2 has an explicit disposition | [ ] |
| Sanitized real-vault soak | At least 24 hours, preferably 3–7 days: flag-off/on cycles, restarts, watcher create/edit/rename/delete convergence, controlled recovery, and unchanged Markdown fingerprints outside explicit fixture changes | [ ] |
| Installed-wheel upgrade and recovery | `2.0.0a5` → `2.0.0b1` on a copied vault; compatible generation/meta preserved; schema mismatch and injected rebuild failure recover safely without partial reads or Markdown writes | [x] — r4 |
| Final release evidence | Full CI passes, final code audit matches the intended scope, and the candidate wheel is built and smoke-tested outside the checkout | [ ] |

## Estimated Impact

The beta does not change the default read path, vault write authority, or Phase 4 scope. Operators who leave `MATRYCA_SHADOW_DB_ENABLED` unset or false retain the established Markdown and generational-BM25 behavior. Operators who opt in receive Shadow reads only while health is `ready`; otherwise fallback remains mandatory.

## Files Involved

- `src/graph/bounded_page_parse.py` and `src/graph/ast_cache.py` — bounded AST parsing and cache publication
- `src/shadow/bootstrap.py`, `src/shadow/sync.py`, and `src/shadow/health.py` — Shadow recovery, health, and fallback
- `tests/test_ast_cache_bounded_parse.py` and `tests/test_shadow_bounded_parse.py` — containment contract
- `docs/roadmaps/ROADMAP_V2_PREPARATION.md` and `docs/roadmaps/ROADMAP_V2_SHADOW_DB.md` — public scope and rollout status

---

**Epic link:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)
_Closes only after the beta is published with all gates above complete and release evidence recorded._
