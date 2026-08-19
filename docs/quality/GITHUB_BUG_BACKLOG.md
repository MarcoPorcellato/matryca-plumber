---
type: Document
---
# GitHub bug backlog — Expert Audit 2026-06 slice

**Triage 2026-07-01:** 33 audit/observability issues closed on GitHub (shipped v1.11.2); pass 2 closed #42, #91, #92; pass 3 closed #38, #113; pass 4 closed #97 (OCC filesystem docs). Session log: [`ISSUE_TRIAGE_2026-07-01.md`](ISSUE_TRIAGE_2026-07-01.md). Epic **#20** pinned.

Authoritative triage matrices:

- [`EXPERT_AUDIT_TRIAGE_2026-06.md`](EXPERT_AUDIT_TRIAGE_2026-06.md)
- [`REPOmix_AUDIT_TRIAGE_2026-06.md`](REPOmix_AUDIT_TRIAGE_2026-06.md)
- [`CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md)
- [`CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md)

## Shipped in v1.11.2 (2026-06-24)

| Issue | Priority | Area | Status |
|-------|----------|------|--------|
| [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132) | P1 | `lock_backoff` downgrades `processed` | fixed |
| [#133](https://github.com/MarcoPorcellato/matryca-plumber/issues/133) | P1 | `graph_dispatch` resolve/write TOCTOU | fixed |
| [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) | P1 | graph→daemon post-write inversion | shipped v1.11.2 |
| [#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) | P2 | Tana streaming graph builder | fixed — single-pass `from_export` + slim payloads ([#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154)) |
| [#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136) | P2 | Generational cache LRU | fixed |
| [#137](https://github.com/MarcoPorcellato/matryca-plumber/issues/137) | P2 | Phase 2 progress regression | fixed |
| [#138](https://github.com/MarcoPorcellato/matryca-plumber/issues/138) | P2 | TUI daemon state dedup load | fixed |
| [#140](https://github.com/MarcoPorcellato/matryca-plumber/issues/140) | P2 | Identity AST stale on mtime reload | fixed |
| [#141](https://github.com/MarcoPorcellato/matryca-plumber/issues/141) | P3 | `RoutingHint` enum (good-first) | fixed |
| [#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142) | P3 | `SemanticRuntimeConfig` injection | fixed |
| [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) | P1 | `block_vectors.json` in-RAM | partial — default `ondemand`, streaming search/indexer; resident opt-in; SQLite v2 → [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) |
| [#115](https://github.com/MarcoPorcellato/matryca-plumber/issues/115)–[#117](https://github.com/MarcoPorcellato/matryca-plumber/issues/117) | P2 | graph→agent coupling | fixed |
| Observability (#143–#144 local bodies) | P3 | silent catalog/checkpoint failures | shipped v1.11.2 |
| Observability (#145–#151 local bodies) | P3 | daemon state / journey / link registry logs | shipped v1.11.2 |
| [#152](https://github.com/MarcoPorcellato/matryca-plumber/issues/152) / #91 | P3 | `_env_int` / `_env_float` invalid warnings | shipped v1.11.2 |
| [#90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90) | P3 | `_env_bool` dedup (graph/markdown_io/link_verification) | shipped v1.11.2 — `src/utils/env_parse.py` |
| [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) | P3 | env parser DRY (cooperative_yield / harvest_runtime) | shipped v1.11.2 |
| [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) | P3 | OCC `st_mtime_ns` parity on page writes | shipped v1.11.2 (partial) |
| [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) | P1 | Generational BM25/alias cache sig_after TOCTOU | mitigated v1.11.2 (3-attempt retry) |
| [#156](https://github.com/MarcoPorcellato/matryca-plumber/issues/156) | P2 | Tana `scan_existing_tana_ids` streaming scan | fixed in working tree |
| [#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157) | P3 | Page lock registry eviction hardening (+ config `lru_cache` note) | fixed in working tree |

**Already tracked (validated by Claude audit — do not duplicate):** [#48](https://github.com/MarcoPorcellato/matryca-plumber/issues/48) triple daemon checkpoint · [#49](https://github.com/MarcoPorcellato/matryca-plumber/issues/49) catalog save per page · [#50](https://github.com/MarcoPorcellato/matryca-plumber/issues/50) insights triple scan · [#53](https://github.com/MarcoPorcellato/matryca-plumber/issues/53) double Phase-2 read · [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) daemon split · ~~[#38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38) `needs_refresh` seconds~~ **closed pass 3**.

Full matrix: [`CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md).

| [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) | P2 | Tana slim `NodeDump` payloads (extends #135) | fixed in working tree |
| [#39](https://github.com/MarcoPorcellato/matryca-plumber/issues/39) | P1 | `auto_split` child page `page_rmw_lock` | fixed in working tree |

## Open — Expert Audit 2026-06

| Issue | Priority | Area |
|-------|----------|------|
| [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) | v2 | Tana content-aware re-import |

## Clean Architecture Audit 2026-06 (simulated Staff review)

| Finding | Verdict | Tracking |
|---------|---------|----------|
| `page_rmw_lock` masquerading as OCC / lock leak | By design + rejected leak | Repomix P1.3; [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) `st_mtime_ns` parity |
| Tana `json.load()` OOM | Obsolete — `ijson` shipped | Partial RAM: #135 / [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) |
| MCP ↔ AST coupling | DTOs + handler registry shipped | ~~#59~~ closed; ~~#134~~ shipped v1.11.2; #17 |
| BM25 cache SQLite outbox | Rejected — in-process mtime cache; vectors use atomic tmp+replace | **Claude P1-02 is different:** sig_after after build → [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) |
| Config import-time globals | Partially addressed | #57, #142 fixed |
| `PageId` lock normalization | Rejected | `graph_safe_page_path` + resolved lock keys |
| Immediate `domain/ports.py` refactor | Defer v2 | #17, #20 |

Full matrix: [`CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md). **No new P1 issues** from this audit.

## Related existing issues

- [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57), [#90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90)–[#91](https://github.com/MarcoPorcellato/matryca-plumber/issues/91) — env / semantic config centralization (partially addressed by #142)
- [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) — full SQLite shard deferred to v2 [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24)
- ~~[#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)~~ — `graph_dispatch` handler registry shipped (Clean Arch P2.3)
