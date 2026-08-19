---
type: Document
---
## Problem Description

The graph layer (domain I/O) directly imports orchestration modules:

- `src/graph/markdown_blocks.py` → lazy `from ..daemon.post_write_hooks import emit_post_write_commit`
- `src/graph/block_ref_lint.py` → `daemon.ast_cache`
- `src/graph/dashboard.py` → `daemon.ast_cache`
- `src/graph/bootstrap_status.py` → `agent.maintenance_daemon.load_daemon_state`

`post_write_hooks.py` already implements a subscriber pattern (`PostWriteEvent`, `register_post_write_hook`), but the **dependency direction** is inverted: graph calls daemon infrastructure instead of emitting through an injectable port.

This blocks isolated unit testing of graph writes without daemon mocks and complicates v2.0 adapter extraction ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17)).

Note: audit claims about `link_verification.py` and `master_catalog.py` importing daemon are **obsolete** — those files are clean.

## Proposed Architectural Solution

Introduce a thin graph-side port (e.g. `src/graph/post_write.py`):

```python
@dataclass(frozen=True)
class PageWrittenEvent: ...

def register_page_written_handler(handler: Callable[[PageWrittenEvent], None]) -> None: ...

def emit_page_written(...) -> None: ...
```

- `markdown_blocks.atomic_write_bytes` calls `emit_page_written` (graph-local, no daemon import).
- Daemon startup registers `DaemonPostWriteSubscriber` that fans out to AST cache, identity refresh, robot git commit (current `post_write_hooks` logic).

Surgical first slice: invert `markdown_blocks` only; follow up for `ast_cache` reads.

## Estimated Impact

**Medio–Alto** — architecture hygiene prerequisite for v2.0 GraphRepository; improves testability without behavior change.

## Files Involved

- `src/graph/markdown_blocks.py`
- `src/daemon/post_write_hooks.py`
- `src/agent/plumber_entry.py` (hook registration at startup)
- `docs/ARCHITECTURE.md`

---
**Expert Audit 2026-06** · Epic context: [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
