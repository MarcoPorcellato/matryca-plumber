---
type: Document
---
## Problem Description

`src/agent/routing_hint.py` emits L1/L2 routing markers as **magic strings** in HTML comments:

- `L1_candidate`, `L2_default`, `L2_graph_append`, `call_search_graph_resolve_entity_for_entities`

Downstream agents and tests match these literals ad hoc. Typos or drift between modules are not caught by the type checker.

## Proposed Architectural Solution

Introduce a small `RoutingHint` `StrEnum` (or `Literal` + constants module) with `.value` used when formatting `<!-- matryca_routing: hint=... -->` comments. Keep emitted string values **unchanged** for backward compatibility with existing agent parsers.

Add unit tests asserting stable serialized values.

## Estimated Impact

**Basso** — maintainability and contributor safety; no runtime behavior change if values preserved.

## Files Involved

- `src/agent/routing_hint.py`
- `tests/` (new or extend MCP/routing tests)
- `docs/openspec/l1-l2-routing.md` (reference enum names)

---
**Repomix Audit 2026-06** · Good-first candidate · Triage: [`docs/quality/REPOmix_AUDIT_TRIAGE_2026-06.md`](../REPOmix_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
