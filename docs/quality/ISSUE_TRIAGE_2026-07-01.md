# Issue triage — 2026-07-01

**Operator:** Marco Porcellato (maintainer)  
**Baseline:** 89 open → **50 open** after pass 1 (−33) + pass 2 (−3) + pass 3 (−2) + pass 4 (−1)

## Pass 1 (2026-07-01)

### Closed as shipped on `main` (33)

| Range | Theme |
|-------|--------|
| #39, #132–#142, #153, #155–#157, #154 | Expert / Claude / Repomix audit — v1.11.2 |
| #143–#152 | Tier E observability silent-failure slices |
| #57, #85, #90, #53, #56, #69, #71 | Performance / env_parse / good-first slices shipped |

Each closure comment links `GITHUB_BUG_BACKLOG.md` and invites reopen with repro on current `main`.

### Pinned

- **Issue #20** — Epic v2 Shadow DB (GraphQL `pinIssue`)
- **Discussion #19** — Core Architecture Evolution RFC (not API-pinnable; visibility via pinned Epic #20)

## Pass 2 (2026-07-01)

### Closed as shipped (3)

| Issue | Reason |
|-------|--------|
| #42 | Parent flock bug — `purge_expired_semantic_cache` + `load_semantic_clusters` use `cross_process_json_flock` |
| #91 | `markdown_io` imports `env_bool` / `env_int` from `utils.env_parse` |
| #92 | Regression test `test_harvest_skips_catalog_upsert_when_semantic_index_occ_aborts` exists |

### Good-first refresh

- Maintainer bump on **#125, #126, #129** (Tier D) and **#168–#173** (Tier F) — link to `docs/FIRST_CONTRIBUTION.md`
- **#51** annotated: partial `ondemand` mode shipped; full fix deferred to v2 [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24)

### Updated docs

- [`good_first_issues_blueprints.md`](../../good_first_issues_blueprints.md) — active candidate list

## Pass 3 (2026-07-01)

### Closed as shipped (2)

| Issue | Reason |
|-------|--------|
| #38 | `needs_refresh` uses `st_mtime_ns` + `_stored_mtime_matches` (legacy second rows); tests in `tests/test_master_catalog.py` |
| #113 | `_count_catalog_summaries` logs on `CatalogLoadError` / `OSError` / `BoundedJsonError`; test in `tests/test_graph_analytics.py` |

### Good-first refresh

- Maintainer bump on **#43, #52, #114** — link to `docs/FIRST_CONTRIBUTION.md`

### Performance backlog annotated (keep open)

- **#46, #47, #48, #49, #50, #54, #55** — confirmed real v1.9.11 performance backlog on `main`; not duplicates of pass 1–2 audit closures

## Pass 4 (2026-07-01)

### Closed as shipped (1)

| Issue | Reason |
|-------|--------|
| #97 | OCC **filesystem resolution constraints** documented in [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) § Optimistic concurrency control — modern vs legacy FS table |

### Doc sync (stale issue lists)

- [`ROADMAP.md`](../../ROADMAP.md) — good-first open list; #138 marked done
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — open vs shipped good-first split
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) — expanded OCC filesystem constraints (#97)

### Milestone / tech-debt annotated (keep open)

- **#73** — soak tests still missing; milestone v1.9.12 confirmed
- **#116** — `plumber_config` ↔ `llm_url_policy` deferred import cycle still present
- **#117** — `control_room_progress` ↔ `maintenance_daemon` runtime coupling still present
- **#129** — no `tests/test_plumber_modules.py` regression for `[COGNITIVE LLM FAULT]` yet

## Remaining backlog (50 open) — taxonomy

| Bucket | ~Count | Action |
|--------|--------|--------|
| **v2.0** (`label:v2.0`) | 21 | Keep open — milestone v2.0.0 |
| **good first issue** | 14 | Keep open — #43, #52, #114, #125–#129 Tier D, #168–#173 Tier F |
| **Performance audit** (#46–#55, #50, …) | ~11 | Real backlog — v1.9.11 milestone |
| **Tech debt / refactor** (#58, #59, #61, #63, #116, #117) | ~8 | v1.9.12 milestone — schedule or split |
| **Epics / docs** (#99, #73) | 2 | #97 closed pass 4; #73 soak tests open |
| **Enhancement** (#72 MCP filtering) | 1 | Triage priority separately |

## Next triage passes (weekly)

1. ~~**Milestone hygiene** — attach #97, #73 to v1.9.12 or close #97 if docs landed~~ — **done pass 4** (#97 closed; #73 milestone confirmed)
2. ~~**Duplicate audit** — #42 vs #104~~ — **done pass 2** (#42 closed; #93/#104 already closed)
3. **Stale good-first** — Tier D (#125, #126, #129) refreshed 2026-07-01
4. **v2 prep** — ensure #174–#186 labels/milestones align with [`ROADMAP_V2_PREPARATION.md`](../roadmaps/ROADMAP_V2_PREPARATION.md).

## Do not close without code proof

- Performance epics (#48–#50 catalog/daemon checkpoint) — tracked, not shipped.
- `#51` hybrid_block_search RAM — partial (`ondemand`); defer full fix to v2 #24.
- `#42` semantic cache flock — **closed pass 2**.
