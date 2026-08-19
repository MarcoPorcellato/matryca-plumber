---
type: Document
---
## Problem Description

`IdentityConfigStore.reload_if_stale` (`src/daemon/config_layer.py`) treats **config file mtime** as the freshness signal, then loads Telos/Constraints via `_load_from_graph()` → `get_graph_ast_cache(graph_root).get_graph()`.

If `matryca-config.md` (or `matryca/config`) changes on disk but the AST RAM cache has **not yet** invalidated/reloaded that page, `reload_if_stale` can persist **stale identity** until a later watcher event or full graph reload.

Plumber's own writes are mostly safe: `emit_post_write_commit` applies `ast_cache.apply_file_event` **before** registered hooks call `refresh_identity_config`. The gap is **external co-editing** (Logseq desktop) or races where mtime advances before AST catch-up.

Repomix audit P1.4 overstated "partial file read during atomic write" — writes use atomic replace; the real gap is **AST cache coherence**, not raw `read_text()` tearing.

## Proposed Architectural Solution

On identity reload when mtime changes (or `force=True`):

1. Resolve identity page path and call `get_graph_ast_cache(root).apply_file_event(path, "modified")` (or targeted `invalidate_and_reload_page`) **before** parsing.
2. Optionally compare `st_mtime_ns` on the resolved path inside the store lock.

Add regression test: mutate config file on disk, reload identity without AST invalidation hook → assert forced AST refresh path returns updated Telos.

## Estimated Impact

**Medio** — intermittent wrong Telos/Constraints in LLM system prompts and MCP identity blocks during concurrent human edits.

## Files Involved

- `src/daemon/config_layer.py` (`IdentityConfigStore`, `refresh_identity_config`)
- `src/daemon/ast_cache.py`
- `tests/` (identity + ast cache integration)

---
**Repomix Audit 2026-06** · Triage: [`docs/quality/REPOmix_AUDIT_TRIAGE_2026-06.md`](../REPOmix_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
