---
type: Document
---
## Problem Description

`src/semantic/config.py` already centralizes embedding env resolution (`EmbeddingSettings`, `HybridWeights`, `dual_embedding_enabled()`). However `src/semantic/indexer.py` `index_page_blocks` calls `dual_embedding_enabled()` at **call time**, reading `os.environ` indirectly on every indexing invocation.

This makes unit tests depend on env mutation and scatters the "is dual embedding on?" decision outside injectable configuration — minor Dependency Rule leak noted in Repomix audit P2.3.

## Proposed Architectural Solution

1. Add frozen `SemanticRuntimeConfig` dataclass bundling `dual_embedding_enabled: bool`, `EmbeddingSettings`, `HybridWeights` with `from_env()` factory (compose existing helpers).
2. Pass `SemanticRuntimeConfig` into `index_page_blocks` (or a thin `BlockIndexer` wrapper) from daemon/MCP composition roots.
3. Tests construct `SemanticRuntimeConfig(dual_embedding_enabled=True, ...)` without touching environ.

Keep `dual_embedding_enabled()` as a thin re-export for backward compatibility.

## Estimated Impact

**Basso** — testability and consistency with `plumber_config` injection patterns; no operator-visible change.

## Files Involved

- `src/semantic/config.py`
- `src/semantic/indexer.py`
- Call sites in `src/agent/maintenance_daemon.py` / semantic write path
- `tests/test_dual_embedding.py`

---
**Repomix Audit 2026-06** · Related: [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) env centralization · Triage: [`docs/quality/REPOmix_AUDIT_TRIAGE_2026-06.md`](../REPOmix_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
