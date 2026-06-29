# v2.0 Preparation — Maintainer Blueprints

**Visitor SSOT:** [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md)  
**Epic:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Milestone:** [v2.0.0 — Shadow DB & Safe-Sync Architecture](https://github.com/MarcoPorcellato/matryca-plumber/milestone/3)  
**RFC:** [Discussion #19](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

Create issues: `bash scripts/populate_v2_preparation.sh` (idempotent).

**Before opening a v2 PR:** read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`docs/CLEAN_CODE_ARCHITECTURE.md`](docs/CLEAN_CODE_ARCHITECTURE.md), run `make check`, reference phase/slice issue in PR title.

---

## Phase tracking issues

| Phase | GitHub | Summary |
|-------|--------|---------|
| 0 | [#174](https://github.com/MarcoPorcellato/matryca-plumber/issues/174) | v1.9.12 prerequisites — #58, #59, env_parse |
| 1 | [#175](https://github.com/MarcoPorcellato/matryca-plumber/issues/175) | `GraphRepository` Markdown adapter |
| 2 | [#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176) | Shadow incremental sync |
| 3 | [#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177) | Read routing + opt-in flag |
| 4 | [#178](https://github.com/MarcoPorcellato/matryca-plumber/issues/178) | Biological memory + Logseq DB Safe-Sync |

Epic index: [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) (comment with phase table).

## Core sub-issues (existing)

| Issue | Scope |
|-------|-------|
| [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) | `GraphRepository` abstraction |
| [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) | Shadow DB read path |
| [#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) | Safe-Sync write path |
| [#23](https://github.com/MarcoPorcellato/matryca-plumber/issues/23) | Hardware profiler (DX, independent) |
| [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) | Tana content-aware re-import (v2) |

---

## Slice backlog (by phase)

### Phase 1 — Ports

| Body file | GitHub | Summary | Difficulty |
|-----------|--------|---------|------------|
| [`v2-phase1-graph-read-port.md`](docs/quality/issue-bodies/v2-phase1-graph-read-port.md) | [#179](https://github.com/MarcoPorcellato/matryca-plumber/issues/179) | `GraphReadPort` + `MarkdownGraphRepository` + parity tests | 4/10 |
| [`v2-phase1-dispatch-read-delegate.md`](docs/quality/issue-bodies/v2-phase1-dispatch-read-delegate.md) | [#180](https://github.com/MarcoPorcellato/matryca-plumber/issues/180) | One `graph_dispatch` read → port | 4/10 |

**Verify:**
```bash
uv run pytest tests/test_graph_repository.py tests/test_graph_dispatch.py -q
make check
```

### Phase 2 — Shadow sync

| Body file | GitHub | Summary | Difficulty |
|-----------|--------|---------|------------|
| [`v2-phase2-shadow-open-connection.md`](docs/quality/issue-bodies/v2-phase2-shadow-open-connection.md) | [#181](https://github.com/MarcoPorcellato/matryca-plumber/issues/181) | `open_shadow_db` + path sandbox | 3/10 |
| [`v2-phase2-post-write-sync.md`](docs/quality/issue-bodies/v2-phase2-post-write-sync.md) | [#182](https://github.com/MarcoPorcellato/matryca-plumber/issues/182) | `post_write` upsert handler | 5/10 |
| [`v2-phase2-fts5-search.md`](docs/quality/issue-bodies/v2-phase2-fts5-search.md) | [#183](https://github.com/MarcoPorcellato/matryca-plumber/issues/183) | FTS5 query module | 4/10 |

**Verify:**
```bash
uv run pytest tests/test_shadow_schema.py tests/test_shadow_sync.py -q
make check
```

### Phase 3 — Alpha routing

| Body file | GitHub | Summary | Difficulty |
|-----------|--------|---------|------------|
| [`v2-phase3-shadow-env-flag.md`](docs/quality/issue-bodies/v2-phase3-shadow-env-flag.md) | [#184](https://github.com/MarcoPorcellato/matryca-plumber/issues/184) | `MATRYCA_SHADOW_DB_ENABLED` + `.env.example` | 2/10 |
| [`v2-phase3-ui-shadow-health.md`](docs/quality/issue-bodies/v2-phase3-ui-shadow-health.md) | [#185](https://github.com/MarcoPorcellato/matryca-plumber/issues/185) | Sovereign UI shadow health row | 3/10 |

### Phase 4 — Memory + Safe-Sync

| Body file | GitHub | Summary | Difficulty |
|-----------|--------|---------|------------|
| [`v2-phase4-recall-search-method.md`](docs/quality/issue-bodies/v2-phase4-recall-search-method.md) | [#186](https://github.com/MarcoPorcellato/matryca-plumber/issues/186) | `search_graph(method=recall)` stub | 4/10 |

---

## v1 blockers (do not duplicate — link in PRs)

| Issue | Why |
|-------|-----|
| [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) | Daemon modularization for sync hooks |
| [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59) | Dispatch registry for read routing |
| [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) | Vector RAM → shadow shard convergence |

---

## Not good-first for v2

Phase 1+ slices require architecture context (OCC, graph layer, shadow contract). Point new contributors to [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md) Tier F for v1 prep instead.

---

## Labels

| Label | Use |
|-------|-----|
| `v2.0` | All v2 track work |
| `v2-prep` | Phase 0–1 |
| `v2-alpha` | Phase 2–3 shadow |
| `v2-memory` | Biological memory |
| `v2-safesync` | Logseq DB write bridge |

Filter: [open v2.0 issues](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3Av2.0)
