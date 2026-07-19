# v2.0-alpha hardening — tracking issue

## Problem Description

`v2.0.0-alpha.1` ships Axis 1 hardening on the opt-in Shadow DB read cache behind `MATRYCA_SHADOW_DB_ENABLED`. **`v2.0.0-alpha.2`** adds the rename stale-owner fix ([#272](https://github.com/MarcoPorcellato/matryca-plumber/issues/272)) and Axis 2–3 audit probes. **`v2.0.0-alpha.3`** ships the hyphenated FTS fix ([#277](https://github.com/MarcoPorcellato/matryca-plumber/issues/277)). **`v2.0.0-alpha.4`** ships the FTS query length bound ([#279](https://github.com/MarcoPorcellato/matryca-plumber/issues/279)) and completes Axis 4 (**52 pass, 0 xfail**; #278 probe corrected). Before `v2.0.0-rc`, we need a structured hardening campaign: reproduce real failures and edge cases with minimal tests, then land **surgical PRs** per confirmed finding — no monolithic audit-fix PR.

**Baseline:** tag [`v2.0.0-alpha.4`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha.4) (release PR pending merge) · prior [`v2.0.0-alpha.3`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha.3) superseded for new installs.

**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

## Proposed Architectural Solution

Seven-axis audit with severity classification **P0–P3**. Each **confirmed** finding gets:

1. A **minimal reproducer test** (fixture vault, failure injection, read-only where possible).
2. A **child issue** linked below.
3. A **surgical PR** — one concern per PR.

### Severity

| Level | Meaning |
|-------|---------|
| **P0** | Data loss/corruption, sandbox bypass, broken fallback to Markdown/BM25 |
| **P1** | Wrong query results, bootstrap stuck, reproducible race |
| **P2** | Diagnostics, performance regression, edge-case contract gap |
| **P3** | Ergonomics, docs-only |

### RC exit criteria

- **No open P0 or P1** findings.
- Every **P2** either fixed or explicitly accepted with rationale in this table.

### Baseline verification commands

```bash
make ci
uvx --refresh-package matryca-plumber \
  matryca-plumber@2.0.0-alpha.4 read --help
# PyPI normalizes the pin to matryca-plumber==2.0.0a4 (PEP 440); help output does not print version.
# vault soak (flag off + flag on) — see Epic #20 distribution comment
```

---

## Seven axes (checklist)

### Axis 1 — Concurrency & recovery

- [x] Bootstrap vs `post_write` / file watcher (defer + replay) — **A1-DEFER-01/02 pass**
- [x] Two processes on the same vault (daemon + CLI / twin `uvx`) — **A1-PROC-01/02 fixed (#262)**
- [x] SQLite `locked` / writer contention / crash mid-transaction — **A1-SQLITE-01 pass; A1-BOOT-02 accepted**
- [x] `shadow_meta` `ready` coherent with committed page/block generation — **A1-META-01 fixed (#264)**

### Axis 2 — Shadow ↔ Markdown correctness

**Status:** audit probes complete (`tests/test_shadow_hardening_axis2_parity.py`).

- [x] Bootstrap parity (pages, blocks, parentage, order) — **A2-PARITY-01 pass**
- [x] Full rebuild vs incremental equivalent sequence — **A2-PARITY-02/03/05 pass**
- [x] Shadow never writes Markdown — **A2-PARITY-04 pass**
- [x] Watcher create/modify/delete — **A2-WATCH-01 pass**
- [x] Rename on disk — **A2-WATCH-02 fixed ([#272](https://github.com/MarcoPorcellato/matryca-plumber/issues/272))**
- [x] Modify during bootstrap replay — **A2-WATCH-03 pass**
- [x] Journals + encoded page titles — **A2-PARSE-01 pass**
- [x] Unicode, multiline, page properties — **A2-PARSE-02 pass**
- [x] Empty / minimal Markdown — **A2-PARSE-03 pass**
- [x] Parser-tolerant malformed outline — **A2-PARSE-04 pass**
- [x] Intra-page duplicate `block_uuid` rejected — **A2-PARSE-05 pass**
- [x] Delete + recreate same title — **A2-PARSE-06 pass**

### Axis 3 — Routing & fallback

**Status:** audit probes complete (`tests/test_shadow_hardening_axis3_routing.py`).

- [x] Health changes between port selection and query — **A3-SURFACE-02 / health-flip probe pass**
- [x] DB removed/corrupted after `ready` — **A3-HEALTH-03 pass**
- [x] Flag toggled across processes — **A3-FLAG cross-process probe pass**
- [x] Zero-hit and not-found must **not** trigger Markdown fallback — **A3-FTS-01 / A3-SUBTREE-01 pass**

### Axis 4 — FTS5

**Status:** audit probes complete (`tests/test_shadow_hardening_axis4_fts5.py`) — **52 pass, 0 xfail**.

- [x] Special chars, quotes, operators, Unicode — **A4-QUERY-01..09 pass; A4-QUERY-05 fixed (#277); A4-QUERY-07 contract corrected (#278)**
- [x] Very long queries — **A4-QUERY-10 fixed (#279)**
- [x] Limits and deterministic ordering — **A4-RANK-01..04 pass**
- [x] MCP/CLI envelope parity — **A4-CONTENT-06 / A4-FAIL envelope probes pass**
- [x] FTS sync/index parity — **A4-SYNC-01..05 pass**
- [x] Failure injection + fallback contract — **A4-FAIL-01..05 pass**

### Axis 5 — CTE subtree

**Status:** audit probes complete (`tests/test_shadow_hardening_axis5_cte.py`) — **43 pass, 0 xfail** (post-#289 fix).

- [x] Extreme depth / `max_depth` limits — **A5-DEPTH-01..09 ([#289](https://github.com/MarcoPorcellato/matryca-plumber/issues/289) fixed)**
- [x] Sibling `sort_order` + depth-first pre-order — **A5-ORDER-01..04 pass**
- [x] `max_nodes` truncation + wide subtrees — **A5-NODES-01..06 pass**
- [x] UTF-8 byte budget + block-boundary truncation — **A5-BYTES-01..06 pass**
- [x] Cycles, cross-page, orphan anchors — **A5-INTEGRITY-01..06 pass**
- [x] Markdown parity + routing/fallback — **A5-PARITY-01..06 pass**
- [x] Concurrency / snapshot isolation — **A5-CONCURRENCY-01..06 pass** (04–06: reader txn + rebuild window + writer lock)

### Axis 6 — Security & isolation

**Status:** audit probes complete (`tests/test_shadow_hardening_axis6_security.py`) — **24 pass, 0 xfail** (post-#293).

- [x] Path traversal and symlink escape — **A6-PATH-01..07 pass** (Unix-only skip on symlink probes; portable probes always run)
- [x] Sanitized errors (no vault content leak) — **A6-ERRORS-01..07 ([#293](https://github.com/MarcoPorcellato/matryca-plumber/issues/293) fixed)**
- [x] Flag `false` must not create/open/mutate SQLite — **A6-FLAG-01..05 pass** (includes pre-existing DB immutability)
- [x] Shadow DB must never write Markdown — **A6-MD-01..05 pass**

### Axis 7 — Performance

- [ ] Bootstrap at 1k / 10k / 50k blocks
- [ ] FTS/CTE latency p50/p95
- [ ] Memory and lock hold duration
- [ ] Watcher cost on file bursts

---

## Findings table

| ID | Axis | Repro | Sev | Minimal test | Child issue | Status |
|----|------|-------|-----|--------------|-------------|--------|
| A1-PROC-01 | 1 | Cross-process rebuild while SQLite writer active | **P1** | `test_a1_cross_process_rebuild_completes_while_sqlite_writer_active` | [#262](https://github.com/MarcoPorcellato/matryca-plumber/issues/262) | **fixed** (`v2.0.0-alpha.1`) |
| A1-PROC-02 | 1 | Design review | **P1** | `test_a1_rebuild_lock_is_in_process_only_documented_gap` | [#262](https://github.com/MarcoPorcellato/matryca-plumber/issues/262) | **fixed** (`v2.0.0-alpha.1`) |
| A1-META-01 | 1 | Manual meta corruption on fixture DB | **P2** | `test_a1_health_not_ready_when_meta_completed_but_pages_empty` | [#264](https://github.com/MarcoPorcellato/matryca-plumber/issues/264) | **fixed** (`v2.0.0-alpha.1`) |
| A1-BOOT-02 | 1 | Injected page failure mid-rebuild | **P2** | `test_a1_rebuild_injected_failure_preserves_committed_generation` | — | **accepted** — rollback preserves generation; `last_sync_error` forces `error` health (fallback) |
| A1-DEFER-01 | 1 | Watchdog delete deferred + file removed | — | `test_a1_watchdog_delete_during_bootstrap_replays_removal_when_file_gone` | — | **pass** |
| A1-DEFER-02 | 1 | `post_write` during bootstrap | — | `test_a1_post_write_during_bootstrap_replays_after_rebuild` | — | **pass** |
| A1-SQLITE-01 | 1 | Holder keeps `BEGIN IMMEDIATE` | — | `test_a1_sqlite_writer_lock_blocks_incremental_without_meta_corruption` | — | **pass** |
| A2-WATCH-02 | 2 | Page file rename leaves stale shadow row | **P1** | `test_a2_watch_02_rename_file_path_parity` | [#272](https://github.com/MarcoPorcellato/matryca-plumber/issues/272) | **fixed** |
| A2-PARITY-01 | 2 | Bootstrap structural snapshot | — | `test_a2_parity_01_bootstrap_pages_blocks_parentage_order` | — | **pass** |
| A2-PARITY-02 | 2 | Full vs incremental create sequence | — | `test_a2_parity_02_full_rebuild_matches_incremental_create_sequence` | — | **pass** |
| A2-PARITY-03 | 2 | Full vs incremental mutations | — | `test_a2_parity_03_full_rebuild_matches_incremental_mutations` | — | **pass** |
| A2-PARITY-04 | 2 | Shadow read-only on Markdown | — | `test_a2_parity_04_shadow_never_writes_markdown` | — | **pass** |
| A2-PARITY-05 | 2 | Permuted incremental schedules | — | `test_a2_parity_05_equivalent_op_permutations_match_full_rebuild` | — | **pass** |
| A2-WATCH-01 | 2 | Watchdog CRUD parity | — | `test_a2_watch_01_watchdog_crud_matches_incremental_sync` | — | **pass** |
| A2-WATCH-03 | 2 | Bootstrap defer replay | — | `test_a2_watch_03_modify_during_bootstrap_replays` | — | **pass** |
| A2-PARSE-01 | 2 | Journal + encoded titles | — | `test_a2_parse_01_journal_and_encoded_page_title` | — | **pass** |
| A2-PARSE-02 | 2 | Unicode / multiline / properties | — | `test_a2_parse_02_unicode_multiline_and_page_properties` | — | **pass** |
| A2-PARSE-03 | 2 | Empty / whitespace pages | — | `test_a2_parse_03_empty_and_minimal_markdown` | — | **pass** |
| A2-PARSE-04 | 2 | Malformed outline tolerance | — | `test_a2_parse_04_malformed_outline_still_parity` | — | **pass** |
| A2-PARSE-05 | 2 | Duplicate block UUID rejection | — | `test_a2_parse_05_duplicate_block_uuid_raises` | — | **pass** |
| A2-PARSE-06 | 2 | Delete + recreate same title | — | `test_a2_parse_06_delete_and_recreate_same_title` | — | **pass** |
| A3-FLAG-01 | 3 | Flag off → no shadow.sqlite on BM25 read | — | `test_a3_flag_01_false_flag_never_creates_shadow_sqlite` | — | **pass** |
| A3-FLAG-02 | 3 | Flag off → Markdown subtree port | — | `test_a3_flag_02_false_flag_subtree_uses_markdown_port` | — | **pass** |
| A3-FLAG-XPROC | 3 | Per-process flag off ignores parent shadow DB | — | `test_a3_flag_cross_process_false_flag_uses_generational_bm25` | — | **pass** |
| A3-HEALTH-01 | 3 | `disabled` → generational BM25 | — | `test_a3_health_01_disabled_routes_generational_bm25` | — | **pass** |
| A3-HEALTH-02 | 3 | `bootstrapping` → no shadow FTS | — | `test_a3_health_02_bootstrapping_routes_generational_bm25` | — | **pass** |
| A3-HEALTH-03 | 3 | DB removed after ready → BM25 fallback | — | `test_a3_health_03_stale_db_removed_routes_generational_bm25` | — | **pass** |
| A3-HEALTH-04 | 3 | `error` meta → BM25 fallback | — | `test_a3_health_04_error_meta_routes_generational_bm25` | — | **pass** |
| A3-HEALTH-META | 3 | Meta/pages mismatch → Markdown subtree port | — | `test_a3_health_meta_pages_mismatch_subtree_falls_back` | — | **pass** |
| A3-FTS-01 | 3 | Zero FTS hits → empty envelope, no fallback | — | `test_a3_fts_01_zero_hits_no_generational_fallback` | — | **pass** |
| A3-FTS-02 | 3 | Invalid FTS → validation error, no fallback | — | `test_a3_fts_02_invalid_query_no_generational_fallback` | — | **pass** |
| A3-FTS-03 | 3 | Backend failure → generational BM25 | — | `test_a3_fts_03_backend_failure_falls_back_to_generational_bm25` | — | **pass** |
| A3-FTS-04 | 3 | Public errors omit vault secrets | — | `test_a3_fts_04_public_errors_do_not_leak_vault_secrets` | — | **pass** |
| A3-SUBTREE-01 | 3 | Missing UUID → NOT_FOUND, no Markdown fallback | — | `test_a3_subtree_01_missing_uuid_not_found_no_markdown_fallback` | — | **pass** |
| A3-SUBTREE-02 | 3 | Inconsistent shadow → Markdown fallback | — | `test_a3_subtree_02_inconsistent_shadow_falls_back_to_markdown` | — | **pass** |
| A3-SUBTREE-03 | 3 | SQLite error → Markdown fallback | — | `test_a3_subtree_03_sqlite_error_falls_back_to_markdown` | — | **pass** |
| A3-SUBTREE-04 | 3 | Truncation notice preserved | — | `test_a3_subtree_04_truncation_notice_preserved` | — | **pass** |
| A3-SURFACE-01 | 3 | MCP BM25 ≡ direct resolver envelope | — | `test_a3_surface_01_bm25_mcp_handler_matches_direct_resolver` | — | **pass** |
| A3-SURFACE-02 | 3 | CLI subtree ≡ port; selector side-effect free | — | `test_a3_surface_02_subtree_handler_matches_port_and_selector_is_side_effect_free` | — | **pass** |
| A3-HEALTH-FLIP | 3 | Health flip after port selection → Markdown fallback | — | `test_a3_health_change_between_port_selection_and_subtree_query` | — | **pass** |
| A4-QUERY-05 | 4 | Unquoted hyphenated query → generational BM25 fallback | **P1** | `test_a4_query_05_hyphenated_phrase_no_generational_fallback` | [#277](https://github.com/MarcoPorcellato/matryca-plumber/issues/277) | **fixed** (PR pending) |
| A4-QUERY-07 | 4 | Invalid probe: `cafe` vs `caffè` (orthography, not diacritics) | **P2** | `test_a4_query_07_unicode_diacritic_fold` | [#278](https://github.com/MarcoPorcellato/matryca-plumber/issues/278) | **invalid expectation** — probe corrected (#287) |
| A4-QUERY-10 | 4 | No bounded max FTS query length | **P2** | `test_a4_query_10_very_long_query_bounded` | [#279](https://github.com/MarcoPorcellato/matryca-plumber/issues/279) | **fixed** (`v2.0.0-alpha.4`) |
| A4-QUERY-01 | 4 | Simple token match | — | `test_a4_query_01_simple_token` | — | **pass** |
| A4-QUERY-02 | 4 | Multi-token implicit AND | — | `test_a4_query_02_multiple_tokens` | — | **pass** |
| A4-QUERY-03 | 4 | Quoted phrase / hyphenated body | — | `test_a4_query_03_quoted_phrase` | — | **pass** |
| A4-QUERY-04 | 4 | Boolean OR + parentheses | — | `test_a4_query_04_operators_and_parentheses` | — | **pass** |
| A4-QUERY-06 | 4 | Apostrophe → validation error | — | `test_a4_query_06_apostrophe_raises_validation_not_sqlite` | — | **pass** |
| A4-QUERY-08 | 4 | Whitespace-only → empty hits | — | `test_a4_query_08_whitespace_only_returns_empty` | — | **pass** |
| A4-QUERY-09 | 4 | Unbalanced quotes rejected | — | `test_a4_query_09_invalid_syntax_validation_error` | — | **pass** |
| A4-CONTENT-01 | 4 | Page title not FTS-indexed | — | `test_a4_content_01_block_body_indexed_not_page_title` | — | **pass** |
| A4-CONTENT-02 | 4 | Block properties not FTS-indexed | — | `test_a4_content_02_properties_not_indexed` | — | **pass** |
| A4-CONTENT-03 | 4 | Unicode body searchable | — | `test_a4_content_03_unicode_in_body` | — | **pass** |
| A4-CONTENT-04 | 4 | Markdown punctuation in body | — | `test_a4_content_04_markdown_punctuation_in_body` | — | **pass** |
| A4-CONTENT-05 | 4 | Multiline block content indexed | — | `test_a4_content_05_multiline_block_content` | — | **pass** |
| A4-CONTENT-06 | 4 | Public envelope omits SQLite internals | — | `test_a4_content_06_public_envelope_omits_raw_db_paths` | — | **pass** |
| A4-RANK-01 | 4 | BM25 relevance ordering | — | `test_a4_rank_01_bm25_ordering_higher_relevance_first` | — | **pass** |
| A4-RANK-02 | 4 | Stable tie-break across connections | — | `test_a4_rank_02_tie_break_stable_across_connections` | — | **pass** |
| A4-RANK-03 | 4 | Limit clamped [1, 500] | — | `test_a4_rank_03_limit_boundaries` | — | **pass** |
| A4-RANK-04 | 4 | Zero hits → no generational fallback | — | `test_a4_rank_04_zero_hits_no_generational_fallback` | — | **pass** |
| A4-SYNC-01 | 4 | Full rebuild ≡ incremental FTS rows | — | `test_a4_sync_01_full_rebuild_matches_incremental_create` | — | **pass** |
| A4-SYNC-02 | 4 | Update removes stale FTS tokens | — | `test_a4_sync_02_update_removes_stale_tokens` | — | **pass** |
| A4-SYNC-03 | 4 | Delete removes FTS hits | — | `test_a4_sync_03_delete_removes_hits` | — | **pass** |
| A4-SYNC-04 | 4 | Rename → single FTS row | — | `test_a4_sync_04_rename_no_duplicate_hits` | — | **pass** |
| A4-SYNC-05 | 4 | Repeated rebuild → no duplicate FTS rows | — | `test_a4_sync_05_repeated_rebuild_no_duplicate_fts_rows` | — | **pass** |
| A4-FAIL-01 | 4 | Missing FTS table → single generational fallback | — | `test_a4_fail_01_missing_fts_table_falls_back_once` | — | **pass** |
| A4-FAIL-02 | 4 | SQLite locked → generational fallback | — | `test_a4_fail_02_sqlite_locked_falls_back_to_generational` | — | **pass** |
| A4-FAIL-03 | 4 | Health `error` skips shadow FTS | — | `test_a4_fail_03_health_not_ready_skips_shadow_fts` | — | **pass** |
| A4-FAIL-04 | 4 | Validation errors bounded, no secret leak | — | `test_a4_fail_04_backend_exception_bounded_public_error` | — | **pass** |
| A4-FAIL-05 | 4 | Writer lock → SQLite error, meta intact | — | `test_a4_fail_05_writer_lock_does_not_corrupt_fts_meta` | — | **pass** |
| A5-DEPTH-04 | 5 | `max_depth=1` with descendants → reports `COMPLETE` | **P2** | `test_a5_depth_04_max_depth_one_with_child_truncated` | [#289](https://github.com/MarcoPorcellato/matryca-plumber/issues/289) | **fixed** |
| A5-DEPTH-05 | 5 | `max_depth=0` (clamped to 1) same truncation status gap | **P2** | `test_a5_depth_05_max_depth_zero_clamped_truncated` | [#289](https://github.com/MarcoPorcellato/matryca-plumber/issues/289) | **fixed** |
| A5-DEPTH-09 | 5 | `max_depth=-5` (clamped to 1) same truncation status gap | **P2** | `test_a5_depth_09_negative_max_depth_clamped` | [#289](https://github.com/MarcoPorcellato/matryca-plumber/issues/289) | **fixed** |
| A5-DEPTH-01 | 5 | 32-block chain under default `max_depth` | — | `test_a5_depth_01_linear_chain_complete_within_default_max` | — | **pass** |
| A5-DEPTH-02 | 5 | Leaf anchor single node | — | `test_a5_depth_02_leaf_anchor_single_node` | — | **pass** |
| A5-DEPTH-03 | 5 | Root anchor includes descendants (pre-order) | — | `test_a5_depth_03_root_anchor_includes_descendants` | — | **pass** |
| A5-DEPTH-06 | 5 | `max_depth` matching chain length | — | `test_a5_depth_06_exact_depth_limit_on_chain` | — | **pass** |
| A5-DEPTH-07 | 5 | Chain longer than `max_depth` → `TRUNCATED` | — | `test_a5_depth_07_depth_limit_plus_one_truncated` | — | **pass** |
| A5-DEPTH-08 | 5 | Default `max_depth=64` caps deep chain | — | `test_a5_depth_08_default_cap_truncates_beyond_64_levels` | — | **pass** |
| A5-DEPTH-09 | 5 | Negative `max_depth` clamped | — | `test_a5_depth_09_negative_max_depth_clamped` | — | **pass** |
| A5-ORDER-01 | 5 | Siblings ordered by `sort_order` | — | `test_a5_order_01_siblings_follow_sort_order` | — | **pass** |
| A5-ORDER-02 | 5 | Depth-first pre-order | — | `test_a5_order_02_depth_first_preorder` | — | **pass** |
| A5-ORDER-03 | 5 | Ordering stable across connections | — | `test_a5_order_03_stable_across_connections` | — | **pass** |
| A5-ORDER-04 | 5 | Incremental ≡ full rebuild order | — | `test_a5_order_04_full_rebuild_matches_incremental` | — | **pass** |
| A5-NODES-01 | 5 | `max_nodes=1` anchor only | — | `test_a5_nodes_01_max_nodes_one_returns_anchor_only` | — | **pass** |
| A5-NODES-02 | 5 | Exact `max_nodes` → `COMPLETE` | — | `test_a5_nodes_02_exact_node_limit_complete` | — | **pass** |
| A5-NODES-03 | 5 | `max_nodes` limit+1 → `TRUNCATED` | — | `test_a5_nodes_03_node_limit_plus_one_truncated` | — | **pass** |
| A5-NODES-04 | 5 | Wide subtree many siblings | — | `test_a5_nodes_04_wide_subtree_many_siblings` | — | **pass** |
| A5-NODES-05 | 5 | Node-limit sets `TRUNCATED` status | — | `test_a5_nodes_05_truncation_status_when_node_limited` | — | **pass** |
| A5-NODES-06 | 5 | No duplicate nodes in result | — | `test_a5_nodes_06_no_duplicate_nodes_in_result` | — | **pass** |
| A5-BYTES-01 | 5 | Under byte limit → `COMPLETE` | — | `test_a5_bytes_01_under_limit_complete` | — | **pass** |
| A5-BYTES-02 | 5 | Over limit truncates on block boundary | — | `test_a5_bytes_02_over_limit_truncates_on_block_boundary` | — | **pass** |
| A5-BYTES-03 | 5 | UTF-8 multibyte valid after truncation | — | `test_a5_bytes_03_utf8_multibyte_valid_after_truncation` | — | **pass** |
| A5-BYTES-04 | 5 | Emoji not split mid-codepoint | — | `test_a5_bytes_04_emoji_codepoints_not_split` | — | **pass** |
| A5-BYTES-05 | 5 | Deterministic excerpt across calls | — | `test_a5_bytes_05_deterministic_excerpt_across_calls` | — | **pass** |
| A5-BYTES-06 | 5 | Truncation marker soft budget (documented contract) | — | `test_a5_bytes_06_truncation_notice_documented_soft_budget` | — | **pass** |
| A5-INTEGRITY-01 | 5 | Missing anchor UUID → `NOT_FOUND` | — | `test_a5_integrity_01_missing_anchor_uuid` | — | **pass** |
| A5-INTEGRITY-02 | 5 | Empty anchor UUID → `NOT_FOUND` | — | `test_a5_integrity_02_empty_anchor_uuid` | — | **pass** |
| A5-INTEGRITY-03 | 5 | Cross-page child → `INCONSISTENT` | — | `test_a5_integrity_03_cross_page_child_inconsistent` | — | **pass** |
| A5-INTEGRITY-04 | 5 | Parent cycle → `INCONSISTENT` | — | `test_a5_integrity_04_parent_cycle_inconsistent` | — | **pass** |
| A5-INTEGRITY-05 | 5 | Self-cycle → `INCONSISTENT` | — | `test_a5_integrity_05_self_cycle_inconsistent` | — | **pass** |
| A5-INTEGRITY-06 | 5 | Dangling `parent_rowid` on anchor — bounded walk | — | `test_a5_integrity_06_orphan_parent_rowid_excluded_from_walk` | — | **pass** |
| A5-PARITY-01 | 5 | Shadow excerpt ≡ Markdown repository | — | `test_a5_parity_01_shadow_excerpt_matches_markdown_repository` | — | **pass** |
| A5-PARITY-02 | 5 | `NOT_FOUND` — no Markdown fallback | — | `test_a5_parity_02_not_found_no_markdown_fallback` | — | **pass** |
| A5-PARITY-03 | 5 | `INCONSISTENT` → Markdown fallback | — | `test_a5_parity_03_inconsistent_shadow_falls_back_to_markdown` | — | **pass** |
| A5-PARITY-04 | 5 | SQLite error → Markdown fallback | — | `test_a5_parity_04_sqlite_error_falls_back_to_markdown` | — | **pass** |
| A5-PARITY-05 | 5 | Handler ≡ read port envelope | — | `test_a5_parity_05_handler_matches_port` | — | **pass** |
| A5-PARITY-06 | 5 | Flag off → Markdown port | — | `test_a5_parity_06_flag_false_uses_markdown_port` | — | **pass** |
| A5-CONCURRENCY-01 | 5 | Bootstrapping → Markdown port | — | `test_a5_concurrency_01_bootstrapping_uses_markdown_port` | — | **pass** |
| A5-CONCURRENCY-02 | 5 | Sequential post-sync query sees new blocks | — | `test_a5_concurrency_02_incremental_sync_then_query_consistent` | — | **pass** |
| A5-CONCURRENCY-03 | 5 | Shadow reads do not mutate Markdown | — | `test_a5_concurrency_03_shadow_reads_do_not_mutate_markdown` | — | **pass** |
| A5-CONCURRENCY-04 | 5 | Reader txn isolates incremental sync (old vs new conn) | — | `test_a5_concurrency_04_reader_transaction_isolates_incremental_sync` | — | **pass** |
| A5-CONCURRENCY-05 | 5 | Query during uncommitted rebuild — committed snapshot only | — | `test_a5_concurrency_05_query_during_uncommitted_rebuild_never_hybrid` | — | **pass** |
| A5-CONCURRENCY-06 | 5 | Reader opened before `BEGIN IMMEDIATE` sees committed subtree | — | `test_a5_concurrency_06_reader_sees_committed_generation_during_writer_lock` | — | **pass** |
| A6-PATH-01 | 6 | Sync rejects page path outside graph | — | `test_a6_path_01_sync_rejects_page_outside_graph` | — | **pass** |
| A6-PATH-02 | 6 | Semantic-cache directory symlink escape rejected | — | `test_a6_path_02_shadow_writer_lock_rejects_cache_symlink_escape` | — | **pass** |
| A6-PATH-03 | 6 | `shadow.sqlite` stays under graph cache | — | `test_a6_path_03_shadow_db_path_stays_under_graph` | — | **pass** |
| A6-PATH-04 | 6 | Graph-root symlink supported; helpers stay sandboxed | — | `test_a6_path_04_graph_root_symlink_resolves_and_stays_sandboxed` | — | **pass** |
| A6-PATH-05 | 6 | Page Markdown symlink outside vault rejected | — | `test_a6_path_05_sync_rejects_page_symlink_outside_graph` | — | **pass** |
| A6-PATH-06 | 6 | `shadow.sqlite` symlink to external file rejected | — | `test_a6_path_06_open_shadow_db_rejects_sqlite_symlink_escape` | — | **pass** |
| A6-PATH-07 | 6 | Writer flock symlink to external file rejected | — | `test_a6_path_07_writer_lock_rejects_flock_symlink_escape` | — | **pass** |
| A6-ERRORS-01 | 6 | Subtree NOT_FOUND omits vault secrets | — | `test_a6_errors_01_subtree_not_found_omits_vault_secrets` | — | **pass** |
| A6-ERRORS-02 | 6 | Subtree backend failure omits injected DB path | — | `test_a6_errors_02_subtree_sqlite_failure_fallback_omits_injected_path` | — | **pass** |
| A6-ERRORS-03 | 6 | FTS validation error omits vault content | — | `test_a6_errors_03_fts_validation_error_omits_vault_content` | — | **pass** |
| A6-ERRORS-04 | 6 | Duplicate UUID sync error omits block bodies | — | `test_a6_errors_04_sync_duplicate_uuid_error_omits_block_content` | — | **pass** |
| A6-ERRORS-05 | 6 | INCONSISTENT subtree fallback omits SQLite leak | — | `test_a6_errors_05_inconsistent_subtree_falls_back_without_sqlite_leak` | — | **pass** |
| A6-ERRORS-06 | 6 | FTS backend failure omits injected DB path | — | `test_a6_errors_06_fts_backend_fallback_omits_injected_path` | — | **pass** |
| A6-ERRORS-07 | 6 | State API `last_sync_error` leaks injected path | **P2** | `test_a6_errors_07_state_api_last_sync_error_omits_injected_path` | [#293](https://github.com/MarcoPorcellato/matryca-plumber/issues/293) | **fixed** |
| A6-FLAG-01 | 6 | Flag off — rebuild skips DB creation | — | `test_a6_flag_01_false_flag_skips_rebuild_db_creation` | — | **pass** |
| A6-FLAG-02 | 6 | Flag off — incremental sync no-op | — | `test_a6_flag_02_false_flag_skips_incremental_sync` | — | **pass** |
| A6-FLAG-03 | 6 | Flag off — read port is Markdown | — | `test_a6_flag_03_false_flag_read_port_is_markdown` | — | **pass** |
| A6-FLAG-04 | 6 | Flag off — subtree handler uses Markdown | — | `test_a6_flag_04_false_flag_handler_uses_markdown_subtree` | — | **pass** |
| A6-FLAG-05 | 6 | Flag off — pre-existing DB byte-identical; no open | — | `test_a6_flag_05_false_flag_leaves_preexisting_db_untouched` | — | **pass** |
| A6-MD-01 | 6 | Full rebuild never writes Markdown | — | `test_a6_md_01_full_rebuild_never_writes_markdown` | — | **pass** |
| A6-MD-02 | 6 | Incremental sync never writes Markdown | — | `test_a6_md_02_incremental_sync_never_writes_markdown` | — | **pass** |
| A6-MD-03 | 6 | Subtree reads never write Markdown | — | `test_a6_md_03_subtree_reads_never_write_markdown` | — | **pass** |
| A6-MD-04 | 6 | BM25 search never writes Markdown | — | `test_a6_md_04_bm25_search_never_writes_markdown` | — | **pass** |
| A6-MD-05 | 6 | Direct CTE query never writes Markdown | — | `test_a6_md_05_direct_cte_query_never_writes_markdown` | — | **pass** |

---

## Estimated Impact

**Alto** — gates `v2.0.0-rc` confidence for operators enabling `MATRYCA_SHADOW_DB_ENABLED`.

## Files Involved

- `src/shadow/` (bootstrap, sync, meta, health, connection, writer_lock)
- `src/agent/shadow_graph_repository.py`, `src/agent/graph_read_port.py`
- `tests/test_shadow_hardening_axis*.py` (audit reproducers)
- `docs/quality/issue-bodies/v2-alpha-hardening.md` (this body, SSOT for edits)

---
**Epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Milestone:** `v2.0.0 — Shadow DB & Safe-Sync Architecture`

_Closes when RC exit criteria are met and findings table is empty or P2-only with explicit acceptance._
