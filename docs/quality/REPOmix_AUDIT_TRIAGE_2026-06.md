---
type: Document
---
# Repomix Architectural Audit — Triage (2026-06)

Second external audit (Repomix-based). Cross-reference with [Expert Audit triage](EXPERT_AUDIT_TRIAGE_2026-06.md), v1.9.x audit JSON, and GitHub #46–#64 / #114–#117 dev audit.

**GitHub issues from this triage:** [#140](https://github.com/MarcoPorcellato/matryca-plumber/issues/140)–[#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142).

---

## Scorecard

| Verdict | Count |
|---------|-------|
| Already tracked (no new issue) | 7 |
| Duplicate of Expert Audit #132–#139 | 3 |
| Audit claim inaccurate / obsolete | 4 |
| **New issues opened** | 3 |

---

## P1 — Critical

| ID | Finding | Code reality | Backlog | Action |
|----|---------|--------------|---------|--------|
| P1.1 | Vector store JSON OOM | **Confirmed** — `BlockVectorStore.blocks` dict loads full `block_vectors.json` | [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) (v1.9.x Audit #25) | Comment on #51: Repomix SQLite shard aligns with v2 [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24); no duplicate |
| P1.2 | Tana no streaming | **Wrong** — `ijson` in `load.py`; real gap is O(nodes) **index** dict | [#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) | Expert Audit already filed |
| P1.3 | OCC lock leak on exception | **Wrong** — `page_rmw_lock` uses `try/finally` + `thread_lock.release()`; `platform_lock` context managers release flock | #40 shipped | **Rejected** — document only |
| P1.4 | Identity config race | **Partial** — not torn `read_text`; **AST cache stale** on mtime-based reload | None | **[#140](https://github.com/MarcoPorcellato/matryca-plumber/issues/140)** |

---

## P2 — Structural

| ID | Finding | Code reality | Backlog | Action |
|----|---------|--------------|---------|--------|
| P2.1 | `graph_dispatch` SRP | **Shipped** — handler registry + write runtime split | ~~[#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)~~ closed, [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) closed | No duplicate |
| P2.2 | `IdentityConfigStore` singleton | Registry `get_identity_store()` per graph root; `clear_identity_config_stores()` for tests | [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) ports | Absorbed into layer-inversion track; optional DI later |
| P2.3 | Feature flag in indexer | `semantic/config.py` exists; indexer still calls `dual_embedding_enabled()` at runtime | [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) | **[#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142)** |
| P2.4 | Agent↔daemon coupling | Ports/adapters | [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134), [#115](https://github.com/MarcoPorcellato/matryca-plumber/issues/115), [#116](https://github.com/MarcoPorcellato/matryca-plumber/issues/116), [#117](https://github.com/MarcoPorcellato/matryca-plumber/issues/117) | No duplicate |

---

## P3 — Minor

| ID | Finding | Code reality | Action |
|----|---------|--------------|--------|
| P3.1 | Hardcoded identity paths | **Already centralized** — `resolve_identity_config_path`, `identity_config_page_paths` in `config_layer.py` | Rejected |
| P3.2 | Inconsistent error protocol (`Result` type) | Mixed `dict ok/error` vs exceptions — broad refactor | **Deferred** — note in ARCHITECTURE; no issue v1 |
| P3.3 | Generational cache "block streaming" | **Misunderstood module** — alias/BM25 mtime cache, not per-block JSON | [#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136) |
| P3.4 | Routing magic strings | **Confirmed** — `routing_hint.py` | **[#141](https://github.com/MarcoPorcellato/matryca-plumber/issues/141)** good-first |

---

## Repomix vs Expert Audit overlap

| Repomix theme | Expert Audit issue |
|---------------|-------------------|
| Tana OOM | #135 |
| Generational cache memory | #136 |
| graph_dispatch / layers | #133 (fixed), #134 (fixed), ~~#59~~ shipped |
| Cross-module coupling | #134, dev #115–#117 |

---

## v2.0 recommendations (Hexagonal, event bus, plugins)

Maps to existing north star — **no new epics:**

- [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20), [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17), [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24), Discussion #19
- Post-write event bus partially exists (`post_write_hooks`); full inversion tracked in #134

---

## Maintainer notes

- Repomix audit read **documentation snapshots**, not current code — several P1 claims predate v1.11 Tana `ijson` and v1.10.6 `platform_lock`.
- `page_rmw_lock` + `sweep_matryca_lock_sidecars` already address orphan sidecars; no indefinite lock leak found in code review.
- For large-vault memory, prioritize **#51** (vectors + hybrid search) before ad-hoc SQLite in v1; Shadow DB [#24] is the strategic store migration.
