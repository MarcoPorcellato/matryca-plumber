## [Unreleased]

## [1.12.0] - 2026-06-24

**Prompt Clean Architecture (plan v3) — Tier-1 DI, L0 write safety, SYSTEM_PROMPT fragment assembly**

### Added

- **L0 write safety** — `src/graph/safety/validators.py` (`reject_id_line_deletion`, `reject_protected_zones_modification`) invoked before semantic index commits; `tests/test_safety_validators.py`.
- **Agent instruction router** — root [`AGENTS.md`](AGENTS.md) maps Cursor vs runtime vault audiences; `make agents-check` / `scripts/check_agents_coherence.py` guard path drift, `llms.txt` byte-identity, and `SYSTEM_PROMPT.md` citation.
- **Tier-1 prompt architecture** — `src/agent/prompts/core.py` (`SystemPromptBuilder`, Tier-1A/B templates); domain builders under `semantic_lint/`, `bootstrap/`, `compression/`, `plumber_modules/marpa/`, `plumber_modules/llm_prompts/`, `graph/insights/`; constructor injection on `InstructorLLMClient`.
- **Paradigm SSOT** — [`docs/openspec/logseq-paradigm.md`](docs/openspec/logseq-paradigm.md) → [`docs/openspec/agent/paradigm.md`](docs/openspec/agent/paradigm.md).
- **`SYSTEM_PROMPT.md` assembly** — [`docs/openspec/agent/`](docs/openspec/agent/) fragments, `make build-system-prompt`, `make check-system-prompt` (fragment `build-hash` in generated banner); Soft Gate decision tree in `soft-gate.md`.
- **Prompt hash snapshots** — `tests/prompt_hash_snapshots.json` + `pytest tests/test_daemon_prompts.py --update-prompt-hashes`; `tests/test_llm_client_prompt_injection.py` verifies DI on `InstructorLLMClient`.
- **Assembly guard** — `build_system_prompt.py` fails when `docs/openspec/agent/*.md` exists but is missing from `_assembly_order.txt`.
- **Cursor rule `11-prompt-maintainer`** — on-request trigger→action checklist for prompt fragments, Tier-1 builders, and MCP docstrings; indexed in [`.cursorrules`](.cursorrules) and [`AGENTS.md`](AGENTS.md).

### Changed

- **Semantic lint prompt** — rule (6) dead-zone invariant; harvest/insights prompts aligned to cross-lingual output (no English-only hardcoding).

### Documentation

- **[`docs/PROMPT_ARCHITECTURE.md`](docs/PROMPT_ARCHITECTURE.md)** — Clean Architecture / Clean Code map for Tier-1, L0, Tier-2 assembly; mermaid + ASCII data-flow diagrams.
- **`docs/ARCHITECTURE.md`**, **`README.md`**, **`ROADMAP.md`**, **`PROJECT_DIARY.md`** — harmonized for plan v3 and v1.12.0.

### Changed
- **Tech Debt (#62):** `flock_available()` in `platform_lock.py`; unified `_format_node_markdown` in `matryca_hooks.py`; `BootstrapHarvestStatus` imported from `bootstrap_harvest.py`.

## [1.11.2] - 2026-06-24

**Graph layer boundary refactor, bounded RAM caches, and OCC nanosecond parity**

### Added

- **Graph layer ports** — `src/graph/post_write.py` (`PageWrittenEvent` pub/sub), `src/graph/ast_cache.py` (canonical AST RAM cache + auto-registered post-write delta handler), `src/graph/daemon_checkpoint.py` (read-only `.matryca_daemon_state.json` bootstrap gate without importing `maintenance_daemon`), `src/graph/cognitive_llm.py`, `src/graph/cooperative_yield.py`, `src/graph/harvest_runtime.py`, `src/graph/page_namespace.py`, `src/graph/prompt_constraints.py`, `src/graph/prompt_layout.py`; agent/daemon modules re-export for backward compatibility. Enforced by `tests/test_graph_layer_boundary.py`.
- **Shared env parsing** — `src/utils/env_parse.py` (`env_bool`, `env_int`, `env_float` with invalid-value warnings); adopted across graph, semantic, and agent config paths ([#62](https://github.com/MarcoPorcellato/matryca-plumber/issues/62) partial).
- **Generational cache LRU** — `MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS` (default 4, clamp 1–32) caps concurrent vault alias/BM25 caches ([#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136)).
- **Dual-embedding memory modes** — `MATRYCA_BLOCK_VECTOR_STORE_MODE=ondemand|resident` (default **ondemand**); `MATRYCA_BLOCK_VECTOR_STORE_MAX_GRAPHS` LRU cap; page-scoped streaming merge via `apply_page_block_vector_updates()` ([#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) partial).
- **Phase 2 progress baseline** — `DaemonState.phase2_vault_baseline_total` stabilizes Sovereign UI vault denominator when live totals shrink ([#137](https://github.com/MarcoPorcellato/matryca-plumber/issues/137)).
- **`SemanticRuntimeConfig`** — injectable embedding/hybrid settings for the semantic indexer path.

### Changed
- **Graph → daemon dependency inversion ([#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134))** — `markdown_blocks.atomic_write_bytes` emits `graph.post_write.emit_page_written`; daemon `post_write_hooks` is a thin adapter; AST refresh registers as a graph-local handler.
- **Agent → graph moves** — cooperative yield, prompt layout/constraints, cognitive LLM protocols, harvest runtime, and page namespace detection canonical in `src/graph/`; agent modules re-export.
- **OCC mtime nanoseconds ([#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) partial)** — `occ_snapshot` / `read_file_mtime_ns` / exact `st_mtime_ns` drift checks on page writes (legacy second-resolution snapshots preserved).
- **`graph_dispatch` write_outline TOCTOU ([#133](https://github.com/MarcoPorcellato/matryca-plumber/issues/133))** — resolve + write run in one `asyncio.to_thread` sync function.
- **`bootstrap_status.collect_bootstrap_status`** — reads checkpoint via `graph.daemon_checkpoint`, not full daemon state load.
- **Generational alias build retry** — up to 3 attempts when `sig_before != sig_after` during concurrent writes ([#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) mitigation).
- **Journal detection in graph layer ([#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71) partial)** — `is_journal_page_title_in_index()` in `alias_index`; cached wrapper in `generational_cache`; injectable `alias_index` on `should_skip_entity_overlap_pair`.
- **Observability** — daemon state/checkpoint `.bak` restore/copy failures, link-registry merges, journey-log upsert, and watcher deletes now log exceptions instead of silent `suppress(OSError)`.
- **Documentation** — README, `llms.txt`, ROADMAP, ARCHITECTURE, PROJECT_DIARY harmonized for **v1.11.2** with layer-boundary Mermaid diagrams and memory-budget flow.
- **Quality triage — Claude Architectural Audit 2026-06-24** — [`docs/quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](docs/quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md); GitHub [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155)–[#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157).
- **Quality triage — Clean Architecture Audit 2026-06** — [`docs/quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](docs/quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md); [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153), [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154).
- **Contributor onboarding** — Good-first [#118](https://github.com/MarcoPorcellato/matryca-plumber/issues/118) shipped via @blackwolf225 ([#122](https://github.com/MarcoPorcellato/matryca-plumber/pull/122)); **Tier E** backlog [#143](https://github.com/MarcoPorcellato/matryca-plumber/issues/143)–[#152](https://github.com/MarcoPorcellato/matryca-plumber/issues/152) — see [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md).
- **Repomix pack** — `repomix.config.json` `include` allowlist aligned with code-graph clusters; `.repomixignore` deduplicated.
- **Repository hygiene (TRIZ separation-in-space)** — vendor graph indexer tooling under gitignored `.local/`; public wrappers `scripts/provision-local-workspace.sh` and `scripts/reindex-code-graph.sh`.

### Fixed

- **Lock backoff downgrade ([#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132))** — skip re-backoff when file was already `processed`.
- **TUI daemon state load ([#130](https://github.com/MarcoPorcellato/matryca-plumber/issues/130))** — narrow exception catch + breadcrumb log.
- **Journal link registry ([#131](https://github.com/MarcoPorcellato/matryca-plumber/issues/131))** — log merge failures during structural settle.
- **Journal settle (#128)** — link registry merge failures during journal structural settle log exception details while preserving non-blocking settle flow.
- **CI / deps ([#118](https://github.com/MarcoPorcellato/matryca-plumber/issues/118))** — `httpx2>=2.4.0` in `[project.optional-dependencies] dev` silences `StarletteDeprecationWarning` from `fastapi/testclient` during tests (thanks to @blackwolf225 in #122).

## [1.11.1] - 2026-06-23

**Logseq Matryca Parser 1.4.0 alignment**

### Changed

- **`logseq-matryca-parser`** — minimum dependency raised to **1.4.0** (from `>=1.3.1`); inherits parser **1.3.x** public API and graph parity, plus **1.4.0** robustness: 31 bug-hunt fixes, canonical page iteration, case-insensitive tag/search, live watcher delete/move handling, SYNAPSE embed safety.
- **Ruff format** — `tags.py`, `write.py`, `test_tana_convert.py`, `test_tana_tags.py` aligned with `make ci` format-check.

## [1.11.0] - 2026-06-23

**Tana → Logseq OG migration**

### Added

- **Tana workspace JSON import** — Full pipeline: [`src/agent/importers/tana/`](src/agent/importers/tana/) (`ijson` streaming, `logseq/config.edn` journal routing, hybrid placement, depth-split, catalog + in-flight wikilink resolution, `tana-id` idempotent OCC writes, `Tana/Import Log` ledger); orchestrator [`src/agent/tana_import.py`](src/agent/tana_import.py); CLI **`matryca import tana --file … [--apply]`** (dry-run default, JSON stdout); MCP **`import_tana`** (`dry_run=True` default). OpenSpec: [`docs/openspec/tana-import.md`](docs/openspec/tana-import.md). Tests: `tests/test_tana_*.py`, `tests/test_tana_e2e.py`.
- **v2.0 roadmaps** — Maintainer checklists for Shadow DB ([#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24)) and Nacre-inspired biological memory layer: [`docs/roadmaps/ROADMAP_V2_SHADOW_DB.md`](docs/roadmaps/ROADMAP_V2_SHADOW_DB.md), [`docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md`](docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md); cross-links in [`ROADMAP.md`](ROADMAP.md) and [`docs/openspec/README.md`](docs/openspec/README.md).
- **v2.0 shadow schema** — [`src/shadow/schema.py`](src/shadow/schema.py) DDL for Logseq read cache (`pages`, `blocks`, `block_refs`, `blocks_fts`) plus biological memory tables (`memory_nodes` through `memory_snapshots`); `apply_shadow_schema()` helper and [`tests/test_shadow_schema.py`](tests/test_shadow_schema.py).
- **v2.0 biological memory decay (Epic #99, Phase A)** — [`src/memory/decay.py`](src/memory/decay.py) Ebbinghaus pure math (`calculate_decayed_weight`, `calculate_stability`, `MemoryEdgeState`) ported from Nacre with numerical parity tests in [`tests/test_decay.py`](tests/test_decay.py).

### Fixed

- **Import cycle (P2)** — Broke `alias_index` ↔ `generational_cache` runtime cycle: pure `is_journal_page_title_in_index(AliasIndex, …)` in domain layer; cached `is_journal_page_title(graph_root, …)` lives in `generational_cache`; `should_skip_entity_overlap_pair` accepts injected `alias_index`.
- **Flaky CI test** — 3000-page semantic clustering scale test moved to `tests/slow/` (`@pytest.mark.slow`, 15s ceiling) after intermittent failures under full-suite load (~9s vs 8s threshold); structural assertions unchanged.
- **Core:** `link_verification` now correctly uses `file_mtime_drifted()` with exact nanosecond precision for OCC checks (thanks to @gaoflow in #88).
- **Daemon shutdown (#44):** Final catalog and daemon state save failures now log exception details instead of being silently suppressed during graceful shutdown (thanks to @gaoflow in #100).
- **Daemon shutdown (#101):** SIGTERM/SIGINT token-log shutdown breadcrumb failures now emit exception details instead of being silently suppressed.
- **TUI dashboard (#102):** Token activity tail and daemon state refresh I/O failures now log exception details while preserving the existing fallback UI.
- **TUI dashboard (#127):** Daemon state load failures now catch only expected state I/O/JSON/value errors and log a breadcrumb before falling back to the cached or empty state.
- **Catalog sync (#103):** Phase-2 post-write catalog updates now persist page mtimes with nanosecond precision.
- **Semantic clusters (#104):** Cluster cache loads now read `semantic_clusters.json` under the shared JSON flock.

### Changed

- **Documentation** — README, `llms.txt`, ROADMAP, ARCHITECTURE, PROJECT_DIARY, OpenSpec index harmonized for **v1.11.0** with Tana import as headline feature; eight-tool MCP surface across `SYSTEM_PROMPT.md`, `agent-dx.md`, `llm-os-instructions.md`, `hermes-agent.md`, `ingest.md` cross-link.
- **Contributor onboarding:** Five good-first issues ([#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101)–[#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105)) shipped via @gaoflow; Tier D backlog ([#125](https://github.com/MarcoPorcellato/matryca-plumber/issues/125)–[#129](https://github.com/MarcoPorcellato/matryca-plumber/issues/129)) — see [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md).
- **Test coverage (#105):** Graceful shutdown tests now assert cleanup still runs after final catalog/state save failures.

## [1.10.6] - 2026-06-19

**Concurrency integrity — unified flock + hub page OCC**

### Fixed

- **JSON sidecar flock parity (#40)** — `cross_process_json_flock` shares `src/utils/platform_lock.py` with page RMW locks: non-blocking acquire with exponential backoff, blocking fallback after NB exhaustion, `MATRYCA_ALLOW_FLOCK_DEGRADATION`, and thread-local reentrancy depth tracking (fixes nested catalog/registry deadlocks and reduces pytest-xdist lock thrashing).
- **Hub page OCC (#34)** — `write_generated_hub_page` in `src/graph/generated_hub_write.py` wraps Master Index and Graph Insights compiles: pre-compile `occ_snapshot`, `page_rmw_lock`, and `atomic_write_bytes_if_unchanged`; concurrent human edits during compile log a graceful skip (derived pages regenerate on the next daemon cycle).

### Changed

- **Documentation** — README, `llms.txt`, ROADMAP, ARCHITECTURE, PROJECT_DIARY harmonized for v1.10.6; new Mermaid diagrams for unified `platform_lock` and hub-page compile writes ([#34](https://github.com/MarcoPorcellato/matryca-plumber/issues/34), [#40](https://github.com/MarcoPorcellato/matryca-plumber/issues/40)).
- **GitHub backlog hygiene** — Closed shipped audit issues #35, #36, #37, #41, #67, #68, #70; tagged six good-first issues (#45, #53, #56, #69, #71, #85) with `good first issue` + `help wanted` and welcome comments; opened [#85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85) for `BootstrapHarvestStatus` Literal dedup (slice of #62). Docs: [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`ROADMAP.md`](ROADMAP.md).
- **`llms.txt` contributor discovery** — Good-first issue filter and scoped task table for agents asking how to contribute to the codebase (`llms.txt`, `.well-known/llms.txt`).

## [1.10.5] - 2026-06-19

**Logseq Matryca Parser 1.3.1 alignment**

### Changed

- **`logseq-matryca-parser`** — minimum dependency raised to **1.3.1** (from `>=1.1.1`); inherits graph parity from 1.2.x (YAML frontmatter, case-insensitive page routing, asset extraction, round-trip fixes) and the 1.3.0 public API surface (`LogosParser`, `SessionAliasRegistry`, `discover_graph_files` at package root).
- **Parser import alignment** — `src/rag/matryca_hooks.py`, `src/agent/ingestion.py`, and `tests/conftest.py` use root-level parser exports; `src/daemon/ast_cache.py` counts bootstrap files via `discover_graph_files` (parser path exclusions).

## [1.10.4] - 2026-06-19

**Dependency maintenance & CI toolchain**

### Changed

- **CI / GitHub Actions** — `actions/checkout@v7` (all workflows, including metrics-saver from v4), `dependency-review-action@v5`, `astral-sh/setup-uv@v8.2.0`.
- **Sovereign UI frontend** — npm patch/minor bumps: `react-dom` 19.2.7, Tailwind CSS 4.3.1 stack, `lucide-react` 1.21.0, `eslint-plugin-react-refresh` 0.5.3.
- **Dependabot** — weekly groups for `github-actions` and `frontend-npm` to reduce PR flood (supersedes Dependabot PRs #75–#82).

## [1.10.3] - 2026-06-18

**Infrastructure hardening & Sovereign UI resilience**

### Changed

- **Sovereign UI API** — `POST /api/config` and graph-path saves offload `.env` I/O and `prepare_matryca_runtime()` to a worker thread so telemetry polling stays responsive during configuration writes; LM Studio model discovery uses `httpx` (no redirects) instead of `urllib`; control-room startup calls `configure_loguru()` for rotating file logs.
- **LLM structured output** — Pydantic LLM/outline models use `extra="forbid"`; OpenAI strict JSON schemas are generated recursively via the SDK helper; completion calls emit `max_completion_tokens` for o-series/gpt-5 models and legacy `max_tokens` for local servers.
- **CodeQL** — workflow query suite narrowed from `security-and-quality` to `security-extended` so Code Scanning reports security findings only (drops maintainability noise such as cyclic-import and unused-variable alerts).

### Security

- **Lock sidecar permissions** — cross-process flock files (`json_flock`, page RMW locks, daemon lock) created with `0o600` instead of `0o644` (CodeQL `py/overly-permissive-file`).

## [1.10.2] - 2026-06-18

**Fast test gate & CI fixes**

### Fixed

- **CI mypy** — `test_semantic_cache_router` patches `time.time` via dotted module path so strict mypy passes (`attr-defined` clean).

### Changed

- **`make test-fast`** — skips `@pytest.mark.integration` subprocess/bootstrap tests; removes real sleeps from TTL and I/O-retry unit tests; adds `make test-integration` for the excluded slice (~4–5s local gate on typical hardware).

## [1.10.0] - 2026-06-18

**Catalog Integrity & OSS Maturity**

### Fixed

- **Harvest catalog drift guard (#37)** — `catalog.upsert` runs only when `_append_minimal_semantic_index` confirms the page write (or the header is already present); OCC abort returns `pending_llm` without catalog/page drift.
- **Link registry atomic save (#41)** — `_save_registry_unlocked` uses `atomic_write_bytes`, matching backlink index and daemon state persistence.
- **Master catalog merge-on-save (#36)** — `MasterCatalog.save()` reloads disk state under flock and merges page rows by `last_mtime` (with explicit `replace=True` for prune); pending `remove()` deltas propagate on merge so harvest and daemon writers no longer clobber each other.
- **Master catalog load flock (#35)** — `load_master_catalog` reads `master_catalog.json` (and `.bak` restore) under `cross_process_json_flock`, matching the save path and `backlink_index` load pattern; backup refresh also runs under flock.
- **Frontend ESLint (react-hooks v7)** — Sovereign UI hooks/components refactored to derived state, `useSyncExternalStore` hydration, and deferred mount fetches; config module exempt from fast-refresh export rule.
- **Flaky xdist test** — `test_bootstrap_harvest_uses_stateless_messages_when_compression_enabled` isolates `LOGSEQ_GRAPH_PATH` and identity injection so parallel workers get deterministic `_completion_messages` output.

### Changed

- **Documentation** — README, `llms.txt`, ROADMAP, ARCHITECTURE, PROJECT_DIARY, OpenSpec index, and Ironclad Shield checklist harmonized for v1.10.0 catalog/registry integrity ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35)–[#37](https://github.com/MarcoPorcellato/matryca-plumber/issues/37), [#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)).
- **`make test-fast`** — caps pytest-xdist at `NUM_WORKERS` (default `4`) to avoid lock thrashing on file-heavy tests; skips `tests/slow/` and `test_security_remediation.py`; adds `make test-full` alias for the coverage gate (`make test` unchanged for CI).
- **OSS / GitHub hygiene** — PR template, CODEOWNERS, [`SUPPORT.md`](SUPPORT.md), frontend ESLint/Vitest in CI, CodeQL, dependency-review on PRs, npm Dependabot, release verify job, version-consistency guard (`scripts/check_version_consistency.py`), PyPI metadata enrichment (720+ tests).

### Security

- **Dependency advisories** — Bump transitive Python packages (`starlette` 1.3.1, `aiohttp` 3.14.1, `cryptography` 49.0.0, `python-multipart` 0.0.32) and frontend toolchain (`vite` 8.0.16+, `esbuild` 0.28.1+, `@babel/core` 7.29.7) to clear open Dependabot alerts.

## [1.9.15] - 2026-06-12

**Strict Mypy Compliance & Journal Phase-2 Bypass**

### Fixed

- **Mypy strictness (#60)** — Removed all 11 `# type: ignore` suppressions under `src/`; replaced with `cast()`, `isinstance()` narrowing, `Path()` coercion, a `_FilesystemObserver` Protocol, and lambda key functions so strict mypy passes without cheats.

### Changed

- **Journal Phase-2 skip** — Daily notes under `journals/` receive Phase-1 structural indexing only (AST cache refresh, link registry, OCC `mtime` ledger); semantic LLM indexing and dual embeddings are bypassed (`src/agent/maintenance_daemon.py`).

## [1.9.14] - 2026-06-10

**Contributor Readiness & Tech Debt Cleanup**

### Added

- **Good First Issues blueprints** — Root [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md) with six curated v1.9.x audit issues and copy-paste GitHub contributor guide comments for external onboarding.

### Fixed

- **SessionAliasRegistry SLF001** — Centralized upstream private dict access in `safe_update_alias` / `safe_alias_items` helpers (`src/agent/alias_state.py`); `graph_tool_helpers.py` no longer mutates `_alias_to_uuid` directly (#64).
- **HTTP NoRedirect DRY** — Shared `NoRedirect` handler in `src/utils/network.py` replaces duplicate classes in `preflight.py` and `ui_server.py` (#62).

### Changed

- **README onboarding** — Narrative hook, Karpathy positioning, non-technical “What it does for you” list, comparison table vs Logseq AI / Obsidian plugins, PyPI Downloads badge; Architecture section moved below Quick Install.
- **Roadmap** — New root [`ROADMAP.md`](ROADMAP.md) (v1.9.x perfection track → v2.0 Shadow DB & Safe-Sync); linked from README Documentation Map.
- **Phase 2 semantic clustering** — Daily journal pages under `journals/` are excluded from Louvain neighborhood clustering and from `[CLUSTER FOCUS]` LLM context injection; they process in a flat `[journals]` group instead of bloating `[unclustered]` (`src/graph/semantic_clustering.py`, `src/agent/maintenance_daemon.py`).
- **Entity consolidation** — Skip `assess_entity_overlap` LLM calls when either title is a `journals/` page or a Logseq daily date string (e.g. `Tue, 22-10-2024`, `2024_10_22`); fixes wasted person-vs-date token spend (#68).

## [1.9.13] - 2026-06-10

**Enterprise Resilience Update — 12 architectural hardening fixes**

### Fixed

#### Security & Sandbox

- **`templates_subdir` path traversal** — `ensure_graph_runtime_directories` rejects `..` segments in wiki YAML `templates_subdir` and falls back to `templates`, so the Vault Sandbox cannot be bypassed via wiki config.
- **Bounded JSON read (TOCTOU)** — `read_bounded_json` reads at most `cap + 1` bytes in a single `open("rb")` call, closing the stat-then-read race that could bypass the memory-DoS cap.

#### RAG & AI Precision

- **Semantic cache key collision** — `semantic_cache_key` prefixes the parent directory name so pages with the same basename in different namespaces no longer share a cache entry.
- **Dual embedding text dedup** — `_block_text` skips identical `content`/`clean_text` pairs so plain blocks are not embedded twice (prevents cosine-score skewing).
- **Subtree heading filter** — `read_subtree_markdown` stops at the matched heading's indent so sibling sections are not leaked into the excerpt (saves tokens, prevents hallucinated context).
- **LLM JSON repair (unbalanced slice)** — `_recover_unbalanced_json_slice` finds the last structural `}`/`]` outside string literals, so truncated payloads with `}` inside values are not silently truncated.
- **LLM JSON repair (array roots)** — `extract_json_payload_regex()` prefers whichever of `{` or `[` appears first, so array-shaped payloads (e.g. `refactor_blocks` **reparent** groups) are no longer collapsed to their leading object; `balance_json_brackets()` closes truncated interleaved structures in correct nesting order (`}]` not `]}`).
- **LLM JSON repair (string-aware trim)** — `strip_trailing_json_garbage()` uses balanced object/array scanning instead of a regex, so `}` / `[` inside string values (code snippets, markdown) are not mistaken for trailing garbage.

#### Core Stability & Automation

- **Block vector store self-heal** — `load_block_vector_store` catches corrupt vector records (`ValueError`/`TypeError`) and falls back to an empty store instead of hard-crashing hybrid search.
- **Journey ledger restore** — `JourneyDayLedger.from_json` coerces corrupt numeric fields via `_coerce_int`, so hand-edited daemon state no longer blocks restart.
- **MCP tool options (`bounded_int_from_options`)** — JSON booleans (`true`/`false`) are rejected instead of silently coercing to `0`/`1` via `int()`.
- **`plumber stop` exit code** — CLI returns non-zero when `stop_daemon` reports `ok: false`, matching `start`/`audit`/`cluster` behavior for automation.
- **Alias index (comma in wikilink)** — `_split_alias_segments` reuses `split_logseq_property_list_values` so `alias:: [[Acme, Inc]], Acme Corp` no longer splits on commas inside `[[wikilinks]]`.
- **Link verification (`*`/`+` bullets)** — `_BULLET_RE` matches `[-*+]` bullets like the rest of `src/graph/`, so URLs/assets on star/plus blocks are extracted and verified.
- **Daemon launch reliability** — PID file is published at foreground worker lock acquisition (before heavy bootstrap); bootstrap `SIGINT`/`SIGTERM` handlers and startup failure paths remove stale PID/lock files; Sovereign UI **Start Engine** spawns `plumber start --foreground` and treats a live published PID as success even when the launcher subprocess exits; stale PID files pointing at live non-Plumber processes return `foreign_pid` instead of being overwritten.
- **CI sandbox-read gate** — `scripts/check_graph_read_sandbox.py` allowlists daemon pid/lock sidecar reads via inline `# sandbox-read-ok` markers instead of brittle hardcoded line numbers.

### Changed

- **Docs** — [`docs/resilience-llm-json-triz.md`](docs/resilience-llm-json-triz.md), [`docs/openspec/security-sandbox.md`](docs/openspec/security-sandbox.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and [`docs/PROJECT_DIARY.md`](docs/PROJECT_DIARY.md) harmonized with the JSON-repair and daemon-launch fixes above.

## [1.9.11] - 2026-06-10

**Sovereign UI reliability — large vault operator fixes**

### Fixed

- **Sovereign UI reliability** — lazy runtime bootstrap (`eager_graph=False`) on settings save, graph-path save, L1 provision, and **Start Engine** so large vaults no longer hit the 10s fetch timeout; `GET /api/config` reads `LOGSEQ_GRAPH_PATH` from `.env` file values; Settings drawer blocks save until config loads, confirms discard on close, and shows API errors (not `engineError`); pre-flight treats `warn` as non-blocking; modal auto-dismisses when checks pass; graph-path pre-flight surfaces post-save verification failures; graph analytics uses 18s server cache, 60s client timeout, and marks telemetry offline on poll failure.

## [1.9.10] - 2026-06-09

**Sovereign UI fast startup — operator command clarity**

### Changed

- **Sovereign UI fast startup** — `matryca plumber status` / `ui` skip eager AST bootstrap in `cli.main()` and use `eager_graph=False` in the UI lifespan so port `8500` and the React shell bind in seconds; graph analytics load on the first dashboard request. **Docs:** `README.md`, `CONTRIBUTING.md`, `docs/ARCHITECTURE.md`, `llms.txt`, and OpenSpec (`runtime-bootstrap`, `agent-dx`, `agent-onboarding`) clarify **`status`/`ui` vs `start`**.
- **Documentation harmonization (v1.9.9)** — `README.md`, `llms.txt` / `.well-known/llms.txt` (§2.4 Security & Sandbox), `SECURITY.md`, `CONTRIBUTING.md`, `SYSTEM_PROMPT.md`, `docs/ARCHITECTURE.md`, and OpenSpec index aligned with v1.9.9 Security & Sandbox code; new [`docs/openspec/security-sandbox.md`](docs/openspec/security-sandbox.md).

## [1.9.9] - 2026-06-09

**Security & Sandbox — v1.9.x perfection track (milestone closure)**

### Security

- **Link verification sandbox** — `_resolve_asset_path` and link-registry `page_relpath` values are validated with `path_sandbox` before any read; traversal refs and tampered registry rows are treated as missing/invalid ([#27](https://github.com/MarcoPorcellato/matryca-plumber/issues/27), [#28](https://github.com/MarcoPorcellato/matryca-plumber/issues/28)).
- **Bounded JSON checkpoints** — graph-local JSON loaders use `read_bounded_json()` with `MATRYCA_JSON_MAX_BYTES` (default 64 MiB) to prevent local memory DoS ([#31](https://github.com/MarcoPorcellato/matryca-plumber/issues/31)).
- **wiki_lint symlink filter** — prefixed page lint skips non-scannable paths via `is_scannable_graph_markdown()` ([#32](https://github.com/MarcoPorcellato/matryca-plumber/issues/32)).
- **LLM debug log hardening** — `MATRYCA_LLM_DEBUG_LOG_PATH` must lie under allowed roots; NDJSON payloads are secret-redacted before append ([#29](https://github.com/MarcoPorcellato/matryca-plumber/issues/29)).
- **UI explicit token default** — `.env.example` templates `MATRYCA_UI_REQUIRE_EXPLICIT_TOKEN=true`; ephemeral-token startup warning cites `/api/config` risk ([#30](https://github.com/MarcoPorcellato/matryca-plumber/issues/30)).
- **Defense-in-depth graph reads** — graph/agent/rag modules migrate to `read_graph_file_text()`; CI `sandbox-read-check` blocks new direct `read_text()` bypasses ([#33](https://github.com/MarcoPorcellato/matryca-plumber/issues/33)).

## [1.9.8] - 2026-06-07

**Documentation harmonization — AX Robustness aligned with code**

### Changed

- **`llms.txt` / `.well-known/llms.txt`** — Bumped to v1.9.8; added §2.3 AX robustness (lenient page titles, `Page Title|block` writes, `warnings` contract), zero-shot mutate example, and anti-patterns for filename hand-crafting.
- **`SYSTEM_PROMPT.md`** — Updated `mutate_graph` / `write_outline` targets, X-Ray pipe form, namespace normalization, and `heading_level` disk contract.
- **`docs/ARCHITECTURE.md`** — New AX robustness component table (`page_input_normalizer`, write target resolver, empty-page writer).
- **`docs/openspec/`** — New [`agent-ax-robustness.md`](docs/openspec/agent-ax-robustness.md); index, `agent-onboarding.md`, and `agent-dx.md` cross-linked.
- **`README.md`** — Current version v1.9.8; agent callout links AX spec.
- **MCP tool docstrings** — `mutate_graph` / `write_outline` documents `Page Title|block` and `warnings` field.

## [1.9.7] - 2026-06-07

**Agent Experience (AX) Robustness & Lenient Resolution**

### Added

- **MCP page-input normalization** — `src/agent/page_input_normalizer.py` leniently resolves agent page titles (`/` ↔ `___`, `.md` / `pages/` stripping, case-insensitive match) at MCP read/mutate/refactor entrypoints without touching `logseq-matryca-parser`.
- **Chaos-hardened AX tests** — `tests/test_agent_experience_robustness.py` stress-tests path traversal rejection, namespace edge cases, and safe fallback writes for hallucinated LLM targets.

### Fixed

- **MCP outline validation** — Automatic type coercion (`int` → `str`) for `heading_level` in `mutate_graph` / `write_outline` payloads; parser echo keys are hoisted from `properties` and stripped before disk write so `heading_level::` never lands in Logseq `.md` files (improves Agent Experience with local LLMs such as Hermes).
- **MCP write resilience** — `write_outline` / `inject_query` with `Page Title|block` targets perform a safe page-bottom append when the block UUID or `[n]` alias is invalid but the page exists; empty or blockless pages append at EOF; warnings are returned in the JSON payload and logged to stderr.
- **MCP input hardening** — Path traversal in page titles is rejected before filesystem lookup; repeated `/` and inline `.md` segments are normalized; integer targets like `0` are coerced safely.

## [1.9.6] - 2026-06-07

### Added

- **Hermes Agent MCP integration** — [`docs/integrations/hermes-agent.md`](docs/integrations/hermes-agent.md) with verified host config, `connect_timeout` vs tool `timeout` guidance, troubleshooting, and `tests/test_hermes_mcp_handshake.py` (stdio `tools/list` within 30 s on a fixture vault).
- **README** — Panoramic Mermaid architecture diagram in the intro (three-surface runtime, shared `graph_dispatch` plane, vault, local LLM); links to [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- **README** — Live GitHub star history chart at the bottom via [star-history.com](https://www.star-history.com) SVG API (`<picture>` with light/dark theme).
- **Release notes** — [`docs/releases/v1.9.6-GITHUB.md`](docs/releases/v1.9.6-GITHUB.md) (GitHub Release copy-paste).

### Changed

- **Lazy AST bootstrap for MCP stdio** — `prepare_matryca_runtime(..., eager_graph=False)` in MCP lifespan defers `LogseqGraph.load_directory` until the first graph tool call; daemon/CLI/UI remain eager. Structured stderr telemetry: `AST cache bootstrap started|complete` with `markdown_files`, `duration_s`, `pages_indexed`.
- **PyPI metadata** — Added Python 3.12/3.13 Trove classifiers so `pypi/pyversions` works after the next PyPI publish.
- **Documentation** — `llms.txt`, `.well-known/llms.txt`, ARCHITECTURE, OpenSpec index, and `agent-onboarding.md` aligned with Hermes host config and lazy MCP handshake (v1.9.6).

### Fixed

- **GitHub traffic badges** — README Shields.io endpoints now read badge JSON from the `metrics` branch (`raw.githubusercontent.com/.../metrics/metrics/...`); `metrics-saver` publishes a metrics-only orphan branch via `METRICS_TOKEN` instead of bloating the branch with the full repo tree.
- **README badges** — Python badge reads `requires-python` from `pyproject.toml` (PyPI `pyversions` showed `missing` without Trove classifiers); coverage anchor and test-count badge aligned with current suite (`640+`, `cov-fail-under=70` at `pyproject.toml` L138).
- **L1 provisioning test** — `tests/test_provision_l1.py` isolates from repo `.env` via `reload_plumber_dotenv` noop so local developer vault paths do not leak into CI/local runs.

## [1.9.5] - 2026-06-05

### Added

- **LLM OS agent contract** — `SYSTEM_PROMPT.md` § "LLM OS" documents two-tier Gardener vs Cognitive Agent architecture, Master Index **Soft Gate** (Local Daemon / Blind Search / Cloud Indexing), and Safe-Sync rules; `llms.txt` §6 points external hosts to the full contract.
- **`read_graph_data` / `bootstrap_status`** — Phase 1 semaphore for MCP and CLI (`matryca --json read bootstrap_status`) exposing `bootstrap_complete`, `soft_gate_active`, harvest progress, and catalog health (`src/graph/bootstrap_status.py`).
- **OpenSpec** — [`docs/openspec/llm-os-instructions.md`](docs/openspec/llm-os-instructions.md) (maintainer single-source spec + v2.0 SQLite migration trigger).
- **L1 starter** — `matryca-l1/llm-os-rules.md` seeded on L1 provision alongside `session-rules.md`.
- **Release notes** — [`docs/releases/v1.9.5-GITHUB.md`](docs/releases/v1.9.5-GITHUB.md) (GitHub Release copy-paste).

### Changed

- **MCP docstrings** — `read_graph_data` and `search_graph` include Soft Gate prerequisite text for Tier-2 agents.
- **Documentation** — README, ARCHITECTURE, PROJECT_DIARY, OpenSpec index, `agent-dx.md`, and `agent-onboarding.md` aligned with the LLM OS contract and `bootstrap_status` read target; `llms.txt` / `.well-known/llms.txt` bumped to v1.9.5.
- **ARCHITECTURE diagrams** — Expanded Mermaid coverage: three-surface runtime, Phase 1→2 state machine, Safe-Sync read/write paths, LLM OS Soft Gate + `bootstrap_status` sequence, `plumber_entry` routing, atomic `ingest_document` pipeline, and richer agent/MCP/CLI dispatch map.

## [1.9.4] - 2026-06-05

### Changed

- **Journey Log** — Daemon duty cycles now upsert a **single cumulative** `- 🤖 Matryca Activity` bullet in today's journal (incrementing daily totals) instead of appending a new `##` section every cycle; idle cycles with no activity skip the write; legacy duplicate sections on today's file are removed on first upsert (`src/agent/journey_log.py`, `src/graph/journal_task_scan.py`).
- **Documentation** — README, ARCHITECTURE, PROJECT_DIARY, OpenSpec [`agent-dx.md`](docs/openspec/agent-dx.md) §4, and `llms.txt` aligned with the consolidated Journey Log contract.

## [1.9.3] - 2026-06-05

### Added

- **Live telemetry (Sovereign UI)** — Cooperative **5-second** checkpoint heartbeat during long LLM work and idle duty-cycle waits; Phase 1 control-room pills flush every `MATRYCA_BOOTSTRAP_PILL_CHECKPOINT_EVERY` pages (default **5**); `GET /api/state` exposes **`daemon_pid`** for background daemon discovery.
- **Env** — `MATRYCA_TELEMETRY_HEARTBEAT_SECONDS`, `MATRYCA_BOOTSTRAP_PILL_CHECKPOINT_EVERY` (documented in [`.env.example`](.env.example)).
- **OpenSpec** — [`docs/openspec/live-telemetry-ui.md`](docs/openspec/live-telemetry-ui.md) (pull-based UI telemetry contract).

### Changed

- **Real-time UI** — Frontend polls `/api/state` on a **5s** cycle; token counters merge live ops-log totals on the API (same policy as the TUI) so counters move during inference, not only on engine stop.
- **Auto-unfreeze** — Sovereign UI detects a live Plumber PID (`daemon_pid` or `running`/`idle` status) and resumes state polling even when started from `matryca plumber start` in another terminal; full logs/analytics still require **Start Engine**.

### Fixed

- **Thread-safe daemon checkpoints** — Telemetry persistence uses `threading.Lock` plus immutable `DaemonState` JSON snapshots so heartbeat threads never race the main LLM loop during `index_page()`.
- **Stuck progress bar & pills** — Progress, bootstrap pills, and Phase 2 file pills reach disk on heartbeat and per-file checkpoints instead of appearing only after **Stop Engine**.

## [1.9.2] - 2026-06-05

### Added

- **Agent onboarding (`llms.txt`)** — `.well-known/llms.txt` standard for autonomous agents (Cursor, Claude Code, Windsurf, Hermes): zero-shot `uvx matryca-plumber` examples, `LOGSEQ_GRAPH_PATH` (no `--graph`), verified `--json read` / `context load` / `plumber audit`, FastMCP stdio (`MATRYCA_MCP_ENABLED`), and anti-patterns to avoid local CLI hallucinations; root `llms.txt` mirror; README agent hook updated.

### Changed

- **Documentation (v1.9.2)** — Aligned README, ARCHITECTURE, PROJECT_DIARY, CONTRIBUTING, SECURITY, SYSTEM_PROMPT, and OpenSpec index with `llms.txt` agent onboarding; added [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md); RELEASE_PROCESS/BRANDING cross-links; test count badges updated to 610+.
- **Dependabot lockfile sync** — `.github/workflows/dependabot-uv-fix.yml` runs `uv lock` on Dependabot PRs and pushes `uv.lock` fixes so CI stays green.
- **README** — Restructured agent/web-scraper entry to prefer PyPI `uvx matryca-plumber` over `git clone`.
- **Dependencies** — Routine bumps: `openai`, `rich`, `packaging`, `mypy`, `pytest-cov` (Dependabot).

### Security

- **Transitive `aiohttp`** — `uv.lock` pins `aiohttp` ≥3.14.0 to remediate upstream CVEs pulled via the dependency tree (Dependabot #5, #6).
- **CLI stdout / CodeQL** — Cleared clear-text-logging false positives: transport layer documents intentional `sys.stdout` use; machine output stays secret-sanitized via `redact_secrets_in_text` and targeted suppressions (`safe_str` helper).

## [1.9.1] - 2026-06-01

### Changed

- **Link verification** — Ruff formatting and minor readability in `src/graph/link_verification.py` and `src/semantic/store.py`; registry batch tests use consolidated mock patches (`tests/test_link_verification.py`).

## [1.9.0] - 2026-06-01

### Added

- **Structural link verification (#15)** — Passive extract of `http(s)://` URLs and local `assets/` paths into `.matryca_link_registry.json`; async HTTP HEAD + filesystem checks on the daemon duty cycle; OCC-safe `dead-link::` / `missing-asset::` block properties after repeated failures (`src/graph/link_verification.py`).
- **Agent-centric DX (#16)** — Global CLI `--json` for machine-readable stdout; `matryca context load` semantic macro; `read subtree` for focused block/header extracts; Journey Log appends `## 🤖 Matryca Activity` to today's journal after each duty cycle (`src/cli/__init__.py`, `src/agent/journey_log.py`, `src/agent/context_load.py`).
- **Documentation (v1.9)** — OpenSpec [`docs/openspec/link-verification.md`](docs/openspec/link-verification.md) and [`docs/openspec/agent-dx.md`](docs/openspec/agent-dx.md); ARCHITECTURE/README/SYSTEM_PROMPT/PROJECT_DIARY aligned with mermaid diagrams for link hygiene and agent DX.
- **Dual embedding strategy (Phase 3)** — Applicability synthesis + dual vectors per block (`vec_content`, `vec_applicability`) in `.matryca_semantic_cache/block_vectors.json`; hybrid cosine retrieval via `search_graph` / `method=semantic`; daemon indexing gated by `MATRYCA_DUAL_EMBEDDING_ENABLED` (`src/semantic/`, `docs/openspec/dual-embedding.md`).
- **Atomic document ingestion (Phase 2)** — **`ingest_document`** MCP tool parses external markdown via OS temp files (never under `pages/`), stamps fresh block UUIDs, appends to daily `Ingest/YYYY-MM-DD` or `MATRYCA_INGEST_PAGE`, and updates `LOG` / `GLOSSARY` ledgers with OCC-safe writes (`src/agent/ingestion.py`, `docs/openspec/ingest.md`).
- **Telos & Identity layer** — In-graph persona on `matryca/config` or `matryca-config` (`- # Telos`, `- # AI Constraints`); reactive refresh via AST cache + file watcher; LLM system-prompt injection; MCP identity footer; **`store_fact`** MCP tool appends durable preferences under AI Constraints on `pages/matryca-config.md` (`src/daemon/config_layer.py`, `src/agent/memory_tools.py`, `docs/openspec/identity-config.md`).
- **Reactive daemon file watching** — `watchdog` observer on `pages/` and `journals/` with debounced change detection (`MATRYCA_WATCH_DEBOUNCE_MS`) wakes the maintenance duty cycle instead of waiting only on poll interval (`src/daemon/file_watcher.py`).
- **In-memory AST cache** — `LogseqGraph` bootstrap and per-file `invalidate_and_reload_page` deltas for MCP/daemon reads (`src/daemon/ast_cache.py`).
- **Surgical robot git commits** — Post-write GitPython commits stage only the modified `.md` file(s) with `robot(matryca): AI auto-update - …` messages; on by default when the graph root is a git repo (`MATRYCA_GIT_ROBOT_COMMIT`, `src/daemon/git_audit.py`).
- **Sovereign UI settings** — Infrastructure drawer exposes `LLM_API_KEY` as **API Token** (password field); persisted to `.env` on save. Required only for cloud OpenAI-compatible endpoints.

### Fixed

- **Journey log pending leak** — After appending `## 🤖 Matryca Activity` to today's journal, the daemon records `journals/YYYY_MM_DD.md` in file state so `list_pending_files` does not re-queue it on the next cycle (`src/agent/maintenance_daemon.py`).
- **Link verification hygiene** — Re-check flagged registry entries; GET fallback when HEAD is inconclusive; merge-safe registry persistence; prune removed page links; clear on-graph `dead-link::` / `missing-asset::` on recovery; journey log splits URL vs asset flag counts (`src/graph/link_verification.py`, `src/agent/maintenance_daemon.py`).
- **Dual embedding durability** — `block_vectors.json` uses cross-process flock + atomic write, survives `clear_semantic_cache`, prunes stale block UUIDs per page, validates embedding dimensions, caps search scan via `MATRYCA_SEMANTIC_SEARCH_MAX_CANDIDATES` (`src/semantic/`).
- **`context load` subtree** — Subtree reads run in a worker thread; invalid `Page|uuid` queries return structured errors instead of raising (`src/agent/context_load.py`).
- **Second-pass hygiene** — Link recovery waits for successful on-graph property clear; block-vector cache reloads when `block_vectors.json` mtime changes; indexer prunes vectors for empty/missing AST pages; metrics workflow uses strict JSON parse and timezone-aware dates (`.github/workflows/metrics-saver.yml`).
- **Third-pass hardening** — Idempotent link flag when hygiene property already exists; bounded GET fallback (404→GET); no strike inflation on already-flagged rows; registry purge when page file deleted; AST-miss indexing skips prune; vector save under instance lock; semantic search cap prefers newest blocks (`src/graph/link_verification.py`, `src/semantic/`).
- **Fourth-pass hardening** — Indexer keeps vectors on transient embed failures; link registry purge on watcher `deleted`; canonical AST page keys for `block_vectors.json`; lexical pre-filter before semantic search cap; bounded GET with range + explicit close; empty-page semantic apply records `skipped` (`src/semantic/`, `src/agent/maintenance_daemon.py`).

### Changed

- **Documentation** — OpenSpec, `SYSTEM_PROMPT.md`, `README.md`, `ARCHITECTURE.md`, `PROJECT_DIARY.md`, and roadmaps aligned for seven MCP tools (`ingest_document` + `store_fact`).
- **Git audit trail** — Retired pre-write `MATRYCA_GIT_SNAPSHOT_ON_WRITE` / `git add -A` snapshots; robot commits run after successful atomic writes via post-write hooks.

### Removed

- **`src/agent/git_snapshot.py`** — Replaced by `src/daemon/git_audit.py` post-write commits.

### Security

- **CLI stdout sanitization** — Machine output masks OpenAI (`sk-`), Anthropic (`sk-ant-`), Bearer, and Logseq credential properties in-place via `redact_secrets_in_text` instead of replacing entire payloads; CodeQL `py/clear-text-logging-sensitive-data` suppressions document stdout as the intentional CLI channel (`src/cli/__init__.py`).

## [1.8.5] - 2026-05-29

### Changed

- **`.env.example`** — Every tunable key documents **Default (code)** vs **Template** values; fixed `MATRYCA_PLUMBER_COMPRESSION_TRIGGER_TOKENS` to `100000`; added `MATRYCA_PLUMBER_NICE_LEVEL`, `MATRYCA_PLUMBER_IONICE_IDLE`, LLM/service-manager notes; `MATRYCA_LLM_PROMPT_CACHE_MODE` marked reserved. CI: `tests/test_env_example_coverage.py`.
- **Cursor rule `07-env-example.mdc`** — Agents must update `.env.example` when env vars change; file split into **Operator essentials** vs **Advanced / high impact** sections.

### Fixed

- **v1.8 audit (round 4)** — `generate_graph_insights` is stateless so ontology reports do not pollute Ermes history; context-compression summaries are prose-sanitized before persistence; semantic-index block catalogs cap at 8k chars; Phase 2 LLM inference no longer holds `page_rmw_lock` (write-only lock in `apply_semantic_page_result`); `id::` lines are excluded from property-line hygiene so Logseq block UUIDs are never edited as properties.
- **Gemma JSON degeneration** — Structured LLM completions cap at `MATRYCA_LLM_MAX_COMPLETION_TOKENS` (default 2048); `json_repair` uses balanced-brace extraction (not greedy `{.*}`), strips post-`}` `\n` token loops, and normalizes Gemma `\n  \"key` leakage before indexing Logseq pages.
- **LLM resilience audit** — Context compression now uses `MATRYCA_LLM_MAX_COMPRESSION_TOKENS`; prose/markdown completions sanitized; Ermes history turns cleaned before append; balanced `[` `]` extraction; collapse of `\t`/`\"` repetition loops; debug NDJSON gated behind `MATRYCA_LLM_DEBUG_JSON`.
- **LLM resilience (round 2)** — Unbalanced/truncated JSON recovery; MCP `parse_json_object` uses `loads_repaired_json`; Path B correction errors stripped of degeneration; cluster focus capped via `MATRYCA_CLUSTER_FOCUS_MAX_CHARS`.
- **Semantic cache hygiene** — `validate_cached_model` evicts schema-invalid or oversize `.matryca_semantic_cache` entries instead of replaying poisoned LLM JSON into the graph pipeline.

### Added

- **Docs** — [`docs/resilience-llm-json-triz.md`](docs/resilience-llm-json-triz.md): TRIZ / resilience-engineering narrative for local LLM JSON (Gemma tail of death, defense-in-depth layers, verification).

## [1.8.4] - 2026-05-29

### Changed

- **README** — Expanded professional badge block at the top (PyPI, GitHub Release, CI quality gates, platform, MCP, Logseq OG, security, contributing, code of conduct).

### Fixed

- **CI** — Pin `astral-sh/setup-uv` to immutable `v8.1.0` (major tag `@v8` was removed in setup-uv v8.0.0).

## [1.8.3] - 2026-05-29

### Fixed

- **CI** — `ruff format` on `maintenance_daemon.py`; GitHub Actions upgraded to Node 24–compatible action majors (`checkout@v6`, `setup-node@v6`, `setup-uv@v8`).

## [1.8.2] - 2026-05-28

### Changed

- **`logseq-matryca-parser`** — minimum dependency raised to **1.1.1** (latest on PyPI; was `>=0.3.3`).

### Fixed

- **Cognitive KV-cache alignment** — `run_cognitive_lint_pipeline` rebuilds `PagePromptSession` after on-disk mutations so semantic index LLM calls no longer use a stale stable prefix.
- **Master catalog load safety** — transient `OSError` no longer caches an empty catalog that could overwrite `master_catalog.json`; corrupt JSON is quarantined or restored from `.bak`; `save()` is blocked until a successful load.
- **Phase 2 page locking** — daemon holds `page_rmw_lock` through cognitive lint, LLM inference, and apply (replacing probe-only locking); in-process lock is re-entrant so nested module writes do not deadlock.
- **Bootstrap failure state** — `bootstrap_failed` persisted in daemon checkpoint; Phase 2 LLM cycles are skipped until Phase 1 succeeds.
- **LLM transport retries** — exponential backoff on transient HTTP errors (`MATRYCA_LLM_TRANSPORT_RETRIES`, default 3).
- **CPU affinity parsing** — invalid `MATRYCA_PLUMBER_CPU_AFFINITY` tokens are logged and skipped instead of crashing startup.
- **`nice_applied` telemetry** — set only when `os.nice` succeeds.

### Security

- **UI token hardening** — startup warning when `MATRYCA_UI_TOKEN` is unset; optional `MATRYCA_UI_REQUIRE_EXPLICIT_TOKEN` refuses UI without an explicit token; `SECURITY.md` / `.env.example` document MCP trust boundary and loopback session risk.

## [1.8.1] - 2026-05-28

### Fixed

- **CI formatting** — `ruff format` on `page_prompt_session.py`, `process_priority.py`, and `master_catalog.py` so `make ci` passes on `main`.

## [1.8.0] - 2026-05-28

### Added

- **v1.8 edge software plan** — [`docs/v1.8-SOFTWARE-EDGE-PLAN.md`](docs/v1.8-SOFTWARE-EDGE-PLAN.md): CPU sandbox, frozen KV prefix, adaptive structured output, mmap reads.
- **Adaptive LLM client** — [`src/agent/llm_client.py`](src/agent/llm_client.py): capability probe, logits JSON-schema fast path, 3-try validation self-correction on legacy servers, `StructuredOutputExhaustedError`.
- **Frozen prompt prefix** — `FrozenPromptPrefix` + SHA-256 verify before LLM calls; `kv_prefix_hash` in ops JSONL.
- **CPU sandbox** — `MATRYCA_CPU_SANDBOX`, optional `MATRYCA_PLUMBER_CPU_AFFINITY`; `psutil` via `[edge]` extra.
- **Mmap graph reads** — [`src/graph/markdown_io.py`](src/graph/markdown_io.py) for Phase 1 bootstrap regex path (`MATRYCA_GRAPH_READ_MMAP`).
- **v1.8 edge computing documentation** — [`docs/v1.8-OPTIMIZATION-PLAN.md`](docs/v1.8-OPTIMIZATION-PLAN.md), [`docs/openspec/llm-performance.md`](docs/openspec/llm-performance.md), ARCHITECTURE / PROJECT_DIARY / README updates.
- **PagePromptSession** — stable per-page LLM prefix reused across cognitive tasks; alias map in capped user block (`MATRYCA_ALIAS_PROMPT_MAX_CHARS`), not system prompt.
- **Stable semantic system prompt** — `semantic_lint_prompts.py` for KV-friendly compiler rules shared by index + cognitive pipeline.
- **Backlink index** — persisted `.matryca_semantic_cache/backlink_counts.json` replaces full-graph rescans during bootstrap.
- **Memory budget** — `release_phase1_memory()`, RSS snapshots (`MATRYCA_RAM_BUDGET_MB`), semantic cache in-process LRU.
- **Cooperative yield** — `yield_host()` during bootstrap; env-tunable intervals and I/O batch pauses.
- **Synthetic graph script** — `scripts/gen_synthetic_graph.py`; slow tests via `make perf` (`pytest -m slow`).

### Changed

- **Documentation** — README, ARCHITECTURE, PROJECT_DIARY, openspec, and v1.8 plans aligned to **1.8.0**; `.env.example` marks legacy `MATRYCA_LM_INSTRUCTOR_*` vars as deprecated (probe-driven `llm_client` Path A/B).
- **Bootstrap harvest** — `build_cache_aligned_prompt` for `harvest_page_summary` and MapReduce reduce; `stateless=True` on per-page LLM paths.
- **BM25 corpus** — postings-lite `doc_term_freqs` (lower RAM); `MATRYCA_BM25_MODE=resident|ondemand`; `release_bm25_corpus()` on Phase 1 teardown.
- **Semantic cache purge** — TTL sweep skips `master_catalog.json`, `backlink_counts.json`, and `semantic_clusters.json`.
- **Daemon** — post-bootstrap `release_phase1_memory()`, cluster precompute after Phase 1, `apply_cpu_sandbox()` / `apply_plumber_priority`, LLM `probe_backend()` at foreground start, `MATRYCA_BOOTSTRAP_CHECKPOINT_EVERY`.
- **Structured output** — `InstructorLLMClient` moved to `llm_client.py`; instructor mode carousel replaced by probe-driven Path A/B.

### Fixed

- **Semantic cache TTL** — no longer deletes the master catalog when purging expired inference cache files.

## [1.7.5] - 2026-05-27

### Added

- **Concurrency preflight** — `probe_concurrency_capability()` and a Sovereign UI checklist row for cross-process `flock` vs in-process-only mode; daemon logs the active contract at startup.
- **`outline_models.py`** — shared `OutlineNode` validation for MCP and `graph_dispatch` (breaks circular import).
- **Tests** — `json_flock`, semantic cache router, page lock probe, bounded JSON ints, LAN UI token policy, in-root symlink sandbox cases.

### Changed

- **Lock-before-LLM** — daemon probes `page_rmw_lock` before paid inference; `lock_backoff` ledger status with exponential retry instead of infinite re-inference.
- **Page lock registry** — refuses growth past 4096 entries (`PageLockUnavailableError`).
- **Semantic cache** — disk read/write wrapped in `cross_process_json_flock`.
- **Path sandbox** — symlinks allowed when resolved target stays under the graph root; `read_graph_file_text` defaults to strict UTF-8.
- **Graph markdown I/O** — `markdown_blocks` reads/writes use strict UTF-8 for vault content.
- **Sovereign UI API** — blocking routes offloaded with `asyncio.to_thread`; daemon start/stop no longer block the event loop; `MATRYCA_UI_ALLOW_LAN` requires an explicit `MATRYCA_UI_TOKEN`.
- **CI** — single `ci.yml` workflow with `make ci` (`ruff format --check` without mutating the tree); Ruff `ASYNC`/`S`/`PERF`/`RUF`; pytest coverage gate (70% on `src`).

### Fixed

- **`graph_dispatch`** — safe integer parsing for JSON tool options (no bare `ValueError` escapes).
- **Phase 2 progress bar (Sovereign UI)** — vault-wide and per-cluster progress now share one resolver with the TUI and daemon checkpoints (`progress_*` on `GET /api/state`); persisted `phase2_cognitive_*` counters and in-flight cluster file subtitles so the bar no longer stays at 0% while the engine works.

## [1.7.0] - 2026-05-27

### Added

- **Pre-flight onboarding (graph + L1)** — Sovereign UI checklist step 2 saves the Logseq test vault path inline; step 3 **Create matryca-l1 folder** calls `POST /api/provision-l1` to provision sibling `matryca-l1/` (README + `session-rules.md`, wiki `memory_path` sync). Template `MATRYCA_L1_PATH` values from `.env.example` are ignored and cleared on provision.
- **Auto `.env` provisioning** — `ensure_repo_dotenv_from_example()` copies `.env.example` → `.env` on first startup (CLI, UI lifespan, `reload_plumber_dotenv`) with a clear Loguru info line.
- **Pre-flight API & wizard** — `GET /api/preflight` validates graph path, L1 memory, and local LLM `/v1/models`; Sovereign UI modal blocks **Start Engine** until all checks pass. Step 3 includes Matryca.ai mission copy, Qwen 3.5 (4B / 1.7B Instruct) sizing, Ministral 3 (3B), and MoE hardware guidance.
- **Branding guide** — [`docs/BRANDING.md`](docs/BRANDING.md): product name **Matryca Plumber** (not “Matryca” alone), Matryca.ai attribution; README, CONTRIBUTING, and pre-flight UI aligned.
- **Runtime bootstrap** (`src/utils/runtime_bootstrap.py`) — `prepare_matryca_runtime()` provisions log directories, sibling `matryca-l1/`, `.matryca_semantic_cache/`, `templates/`, and seeds `matryca-wiki.yml` before harvest or MCP lifecycles (daemon, CLI, Sovereign UI, MCP stdio). Spec: [`docs/openspec/runtime-bootstrap.md`](docs/openspec/runtime-bootstrap.md).
- **L1 directory provisioning** — `ensure_matryca_l1_dir()` creates `<parent-of-vault>/matryca-l1/` with operator docs (`README.md`, not loaded into LLM context) and starter `session-rules.md` when no other content `*.md` exists; override via `MATRYCA_L1_PATH` or `memory_path` in wiki YAML.
- **CI test workflow** (`.github/workflows/test.yml`) — Pytest, Ruff, and Mypy on `main` and pull requests (with Sovereign UI frontend build).
- **Phase 1 catalog pills** — bootstrap harvest persists `bootstrap_recent` (per-page harvest status) so the control room shows live indexing pills during cataloging, not only Phase 2 checkpoints.
- **Page Summaries metric** — `GET /api/graph-analytics` exposes `page_summaries` (master catalog + session ledger); Sovereign UI **Plumber Agent Cognition** panel shows a fourth tile.

### Changed

- **Pre-flight & docs** — Sovereign UI wizard and README recommend only **Gemma 4-E4b Instruct** (`gemma-4-e4b-it`); removed Qwen/Ministral model lists; note on testing additional models for CPU-only 16 GB RAM. `.env.example` default updated to match.
- **README** — documents Sovereign UI pre-flight checklist (operator steps, live checks, `status` vs `start`, `uvx` zero-install), Marco Porcellato · Matryca.ai attribution, and links to `docs/BRANDING.md`.
- **Loguru bootstrap** — `configure_loguru()` delegates log parent-dir creation to the same runtime bootstrap helper as ops JSONL sinks.
- **`.env.example`** — `MATRYCA_L1_PATH` left commented (sibling `matryca-l1/` via pre-flight); documents log path overrides and runtime layout pointers.

### Fixed

- **Phase 1 catalog pills (empty state)** — pills no longer read only `state.files` during Phase 1 when the daemon has not yet started Phase 2 file checkpoints.
- **Phase 1 thermal delay** — bootstrap pauses reload `MATRYCA_THERMAL_DELAY_BOOTSTRAP` from `.env` after every catalog LLM turn (Settings Drawer value is honored); cool-down sleeps wake promptly on Stop.
- **Phase 1 cooperative stop** — bootstrap harvest checks shutdown between pages and during map-reduce chunks instead of running the full vault after Stop.
- **Sovereign UI Stop** — `POST /api/daemon/stop` is exempt from UI rate limiting; the 1s poll loop no longer hammers `/api/config`, avoiding 429 responses that blocked stop requests.
- **Pre-flight graph save** — `POST /api/config/graph-path` (and ``PATCH``) updates only ``LOGSEQ_GRAPH_PATH``; API errors surface in the UI; verified graph clears stale save errors.
- **Sovereign UI start gate** — `GET /api/state` reports `stopped` when no live Plumber PID is present, so opening `status` alone does not imply the engine is running or disable **Start Engine** on a stale `idle` checkpoint.
- **Sovereign UI polling** — `GET /api/state` returns only the daemon checkpoint (no full-graph scan); topology telemetry moves to async `GET /api/graph-analytics` via `asyncio.to_thread`, so the 1s poll loop no longer blocks the FastAPI event loop.
- **Phase 1 progress** — bootstrap harvest persists `bootstrap_scanned` / `bootstrap_total` every 50 pages; the control-room progress bar advances during cataloging instead of staying at 0%.
- **CLI logging** — reject or redact operator payloads that would log secrets in clear text (`secret_violations_in_text` on CLI paths).

## [1.6.1] - 2026-05-25

No user-facing changes (version alignment with PyPI / lockfile).

## [1.6.0] - 2026-05-25

### Added

- **Shared LLM SSRF policy** (`src/utils/llm_url_policy.py`) — `validate_llm_proxy_url()` guards Sovereign UI model discovery, `.env` persistence, and daemon `InstructorLLMClient` outbound calls (metadata IPs, non-HTTP schemes, hostile DNS).
- **Graph path allowlist** — `validate_logseq_graph_path_for_config()` restricts `LOGSEQ_GRAPH_PATH` updates from the Settings UI to home, repo, temp, current graph, and optional `MATRYCA_ALLOWED_GRAPH_ROOTS`.
- **Split UI rate limits** — `MATRYCA_UI_RATE_LIMIT_UNAUTH_PER_MINUTE` (default 30) for anonymous `/api/*` traffic; authenticated budget remains `MATRYCA_UI_RATE_LIMIT_PER_MINUTE` (default 120). `/api/health` and loopback-only `/api/auth/session` are exempt.
- **`MATRYCA_MCP_ENABLED`** — FastMCP stdio is **off by default**; bare `matryca-plumber` exits with guidance until the flag is set (Claude Desktop / Cursor hosts).

### Changed

- **MCP tool errors** — `mcp_tool_guard` returns sanitized messages (no raw filesystem paths) unless `MATRYCA_DEBUG=true`.
- **Sovereign UI default port** — aligned dev API base and Uvicorn default to **8500** (was 8000 in some paths).
- **Sovereign UI frontend** — rebuilt production bundle shipped in the PyPI wheel.

## [1.5.17] - 2026-05-24

### Changed

- **Security modules** — consolidated regex policies and secret-redaction helpers for stricter typing and reuse across CLI, UI, and daemon surfaces.

## [1.5.16] - 2026-05-24

### Changed

- **`uv.lock`** — synced for CI reproducibility (no application logic changes).

## [1.5.15] - 2026-05-24

### Fixed

- **MCP log bridge** — reset/re-register Loguru MCP telemetry sink after `logger.remove()` (fixes flaky `test_mcp_telemetry` under full pytest collection).
- **Sovereign UI daemon start** — treat successful detached launcher exit (code 0) as success when a live PID is published.
- **Optimistic concurrency** — capture OCC baseline before page reads; re-baseline after cognitive lint self-writes; re-check mtime immediately before atomic commit.
- **`plumber_entry`** — lazy-import MCP entrypoint so CLI routing does not load FastMCP at import time.
- **Page lock registry** — LRU eviction of unlocked entries instead of clearing the entire registry at 4096 entries.
- **`.env` persistence** — atomic writes from the Sovereign UI settings drawer.
- **UI auth session** — restrict `/api/auth/session` to loopback clients unless `MATRYCA_UI_ALLOW_LAN=1`; refuse `0.0.0.0` bind without that flag.
- **Daemon PID handling** — return `foreign_pid` when a live non-plumber process holds the PID file; tighten `is_plumber_process` heuristics.
- **Frontend auth** — validate session tokens, fail fast on bootstrap errors, default production API base to `window.location.origin`, polyfill `AbortSignal.any`.

## [1.5.14] - 2026-05-24

### Changed

- **MCP telemetry** — clearer context management in structured MCP log events.

## [1.5.13] - 2026-05-24

### Fixed

- **MCP Loguru sink** — thread-safe `enqueue` pickling for telemetry under pytest and multi-threaded hosts.

## [1.5.12] - 2026-05-24

### Added

- **`matryca-plumber` console router** — route shorthand CLI invocations (`status`, `start`, …) to `matryca plumber` while preserving MCP stdio as the default.

## [1.4.1] - 2026-05-20

### Added

- **`search_graph` / `method=resolve_entity`** — vault-wide alias index resolution via `cached_build_alias_index` (canonical page, collisions, `safe_to_create_new_page`).
- **X-Ray alias support in `read_graph_data` / `block_ast`** — `Page Title|[n]` resolves through `.matryca_xray_state.json` before disk lookup.

### Changed

- **`mutate_graph` / `write_outline`** success responses now include `"ok": true` for a uniform JSON contract.
- **Routing hints** for entity outlines point agents to `search_graph` / `resolve_entity` instead of a removed standalone tool.
- **`.env.example`** — removed obsolete `LOGSEQ_API_*` variables (headless-only since v1.4.0).

### Removed

- **`src/bridge/`** — empty legacy package left after the HTTP client purge.

## [1.4.0] - 2026-05-19

### Added

- **FastMCP integration** — MCP server (`FastMCP`) with stdio transport, lifespan wiring, and five mega-tools (`src/main.py`).
- **Makefile developer experience** — targets for install (`uv`), format, lint, typecheck, test, aggregate `check`, and clean (`Makefile`).
- **GitHub Actions CI** — workflow running Ruff, Mypy, and Pytest on push and pull request to `main` (`.github/workflows/ci.yml`).
- **Pydantic data validation** — hierarchical `OutlineNode` models and validated tool payloads (`src/agent/mcp_server.py`).
- **Apache License 2.0** — project licensing as declared in `LICENSE` and `pyproject.toml`.

### Removed

- **Logseq HTTP JSON-RPC client** — `httpx` / `LogseqClient` / `src/bridge/logseq_client.py` (100% headless disk writes).
