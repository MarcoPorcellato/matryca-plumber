---
type: Document
---
# LLM performance & edge computing (v1.8+)

**Roadmap:** [`../v1.8-OPTIMIZATION-PLAN.md`](../v1.8-OPTIMIZATION-PLAN.md)  
**Related:** Phase 14d Context Acceleration in [`../PROJECT_DIARY.md`](../PROJECT_DIARY.md)  
**Clean Architecture (v1.12):** [`../PROMPT_ARCHITECTURE.md`](../PROMPT_ARCHITECTURE.md) — Tier-1 builders, L0 safety, Tier-2 assembly

Matryca Plumber targets **CPU-only laptops with 16 GB RAM** running a local OpenAI-compatible server (LM Studio, Ollama, llama.cpp). The vault may contain **up to ~10,000** Markdown pages. v1.8 adds **no new semantic features** — only memory governance, KV-cache-friendly prompts, and cooperative I/O so the host OS stays responsive during long harvests.

---

## Clean Architecture boundaries (v1.12)

Robert C. Martin’s **Dependency Rule** applies to prompts: domain `*/prompts.py` modules depend inward on `prompts/core.py` only; use cases (`InstructorLLMClient`, `maintenance_daemon`) depend on builder callables, not inline strings.

```text
  Entities (Pydantic lint models)
       ▲
  Domain (*/prompts.py, safety/validators.py)
       ▲
  Use cases (llm_client, plumber_modules, index commit)
       ▲
  Adapters (build_system_prompt.py, semantic_lint_prompts re-export)
       ▲
  Frameworks (SYSTEM_PROMPT.md, llms.txt, MCP)
```

| Concern | Module | Clean Code note |
|---------|--------|-----------------|
| **SRP** | One `prompts.py` per cognitive domain | No `DaemonPromptRegistry` god-object |
| **DIP** | `InstructorLLMClient(..., builders=...)` | Tests inject fakes (`test_llm_client_prompt_injection`) |
| **Fail fast** | `validate_llm_write_diff` | L0 before OCC write — unsafe LLM output never hits disk |

---

## Design goals

| Goal | Mechanism |
|------|-----------|
| **Zero-Prefill** on repeated tasks per page | Stable user prefix (`Page content:` first, task last); constant system prompt |
| **Bounded RAM** across multi-day daemon uptime | Postings-lite BM25, semantic cache LRU, Phase 1 teardown, optional catalog unload |
| **Host survival** during bootstrap | `yield_host()`, persisted backlink index, thermal pauses, `os.nice` / optional ionice |

---

## Prompt layout contract

Every local LLM call that reads page text should follow:

```text
[System — stable compiler rules, no per-page alias map]
[User — Page content: <stable payload> + optional AliasIndex footer + Task: <dynamic>]
```

### Modules

| Module | Role |
|--------|------|
| [`prompts/core.py`](../../src/agent/prompts/core.py) | `SystemPromptBuilder` protocol, Tier-1A/B compile helpers (domain builders import **only** this module) |
| [`semantic_lint/prompts.py`](../../src/agent/semantic_lint/prompts.py) | Tier-1A semantic lint compiler (rules 1–6) |
| [`bootstrap/prompts.py`](../../src/agent/bootstrap/prompts.py) | Tier-1A harvest summaries |
| [`plumber_modules/marpa/prompts.py`](../../src/agent/plumber_modules/marpa/prompts.py) | Tier-1A MARPA classify |
| [`plumber_modules/llm_prompts/`](../../src/agent/plumber_modules/llm_prompts/) | Tier-1A entity/seed/tag prompts |
| [`compression/prompts.py`](../../src/agent/compression/prompts.py) | Tier-1B session compression |
| [`graph/insights/prompts.py`](../../src/graph/insights/prompts.py) | Tier-1A `GraphInsightsLLMResult` |
| [`graph/safety/validators.py`](../../src/graph/safety/validators.py) | L0 hard rejection before LLM-backed disk writes |
| [`prompt_layout.py`](../../src/agent/prompt_layout.py) | `build_cache_aligned_prompt(content, task_instruction)` |
| [`semantic_lint_prompts.py`](../../src/agent/semantic_lint_prompts.py) | Deprecated re-export → `semantic_lint.prompts` |
| [`page_prompt_session.py`](../../src/agent/page_prompt_session.py) | One `PagePromptSession` per file per daemon cycle |
| [`llm_context_payload.py`](../../src/agent/llm_context_payload.py) | Shrinks giant pages before they enter the stable block |

**Maintainer checklist:** new cognitive module → add domain `prompts.py` builder + extend `tests/test_daemon_prompts.py` (budget, substrings, SHA-256 via `prompt_hash_snapshots.json`).

### Per-page session lifecycle

1. `prepare_llm_context_payload()` produces the reduced body (raw, summary, skeleton, or truncated).
2. Optional **AliasIndex** footer is appended to the stable block (capped by `MATRYCA_ALIAS_PROMPT_MAX_CHARS`, default 2048) — **not** injected into the system prompt (v1.7 and earlier hurt KV reuse).
3. Cognitive modules (MARPA, dangling healer, entity consolidation, property hygiene) reuse the **same** `stable_page_block`.
4. `semantic_index_page`, bootstrap harvest, and **`generate_graph_insights`** use `stateless=True` so Ermes rolling history does not grow the prefix between unrelated operations or one-off reports.
5. When `MATRYCA_PLUMBER_CONTEXT_COMPRESSION=true`, condensation summaries are **`sanitize_prose_llm_completion()`** before they replace dropped history turns (`condense_messages`, `_compress_history_via_llm`).
6. Semantic index prompts include a block UUID catalog capped at **8000 characters** (`_enumerate_blocks_for_prompt`) so pages with hundreds of `id::` lines do not dominate the user block.

### Bootstrap & MapReduce

- **`harvest_page_summary`** uses `build_cache_aligned_prompt` (fixes the pre-v1.8 anti-pattern that placed `Content:` after the task).
- **MapReduce** (`hierarchical_summarization.py`): chunk passes send page trees; the reduce pass sends **section summaries** as stable content and the consolidation instruction as the task tail.

### Cluster mode

When semantic clustering is active, `inject_cluster_focus_context()` seeds neighborhood summaries once per cluster. Set `MATRYCA_LLM_CLUSTER_HISTORY=false` (default) for a minimal assistant ack — better prefix stability than a long synthetic JSON turn in history.

---

## Memory plane

| Component | v1.8 behavior |
|-----------|----------------|
| **BM25** (`generational_cache.py`) | `doc_term_freqs` per page (postings-lite); `MATRYCA_BM25_MODE=resident\|ondemand`; `release_bm25_corpus()` on Phase 1 teardown |
| **Semantic cache** (`semantic_cache_router.py`) | Disk TTL + in-process LRU (`MATRYCA_SEMANTIC_CACHE_MEMORY_ENTRIES`); purge skips reserved JSON (`master_catalog.json`, `backlink_counts.json`, `semantic_clusters.json`) |
| **Master catalog** (`master_catalog.py`) | `unload_master_catalog()` after bootstrap teardown; flock load + merge-on-save under concurrent writers (v1.10.0 — [#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35), [#36](https://github.com/MarcoPorcellato/matryca-plumber/issues/36)) |
| **Memory budget** (`memory_budget.py`) | `release_phase1_memory()`, `snapshot()`, `maybe_release_after_cycle()` |

After successful Phase 1 bootstrap, the daemon calls `release_phase1_memory()` (clear generational caches, release BM25, trim semantic RAM, unload catalog, `gc.collect()`), precomputes semantic clusters, then enters Phase 2 polling.

---

## I/O & CPU plane

| Component | Role |
|-----------|------|
| [`cooperative_yield.py`](../../src/agent/cooperative_yield.py) | `yield_host()` every `MATRYCA_BOOTSTRAP_YIELD_EVERY` files (default 25) |
| [`backlink_index.py`](../../src/graph/backlink_index.py) | Persists `.matryca_semantic_cache/backlink_counts.json`; invalidates on `patch_generational_caches_for_paths` |
| [`process_priority.py`](../../src/agent/process_priority.py) | `apply_cpu_sandbox()` — CPU affinity + `nice(19)` + ionice when `MATRYCA_CPU_SANDBOX=true` (`pip install matryca-plumber[edge]` for `psutil`) |
| [`markdown_io.py`](../../src/graph/markdown_io.py) | `mmap_graph_page()` / `read_graph_page_text()` when `MATRYCA_GRAPH_READ_MMAP=true` |
| **Thermal pauses** (`plumber_config.py`) | `MATRYCA_THERMAL_DELAY_BOOTSTRAP` / `MATRYCA_THERMAL_DELAY_COGNITIVE` after each LLM turn |

---

## Adaptive structured output

| Path | When | Behavior |
|------|------|----------|
| **A** | Probe finds `json_schema` strict support | Single completion via OpenAI `response_format`; `parse_llm_json` after sanitization |
| **B** | Legacy / probe miss | Up to 3 self-correction turns with `ValidationError` feedback; `parse_llm_json` once per attempt |
| **Exhausted** | Path B fails | `StructuredOutputExhaustedError` → page `status=error` (skip until mtime change or restart) |

Module: [`llm_client.py`](../../src/agent/llm_client.py). Foreground daemon calls `probe_backend()` once at start.

### Resilient JSON (TRIZ — local model degeneration)

Small models (e.g. **Gemma 4-E4b**) may omit `<eos>` under strict JSON and enter a **literal `\n` repetition loop**, wasting CPU/RAM without improving the graph. Matryca Plumber applies **defense in depth**:

| Layer | Mechanism |
|-------|-----------|
| Brake | `MATRYCA_LLM_MAX_COMPLETION_TOKENS` (default 2048) on all structured completions |
| Scalpel | First-delimiter balanced extract (`{` or `[`) — **not** greedy `{.*}` regex |
| Filter | `sanitize_llm_completion_text()` + Gemma key/run repair in [`json_repair.py`](../../src/utils/json_repair.py) |
| Salvage | `strip_trailing_json_garbage()` + `balance_json_brackets()` — string-aware trim and nesting-order close for truncated payloads |

Full TRIZ framing, failure anatomy, and verification: **[`resilience-llm-json-triz.md`](../resilience-llm-json-triz.md)**.

### Phase 2 OCC and page lock (daemon)

`_process_llm_cycle_file` follows the canonical OCC order in [`ARCHITECTURE.md`](../ARCHITECTURE.md#optimistic-concurrency-control-occ): **`page_rmw_lock` is not held during LLM inference**. Cognitive modules take short per-operation locks; the semantic index commit acquires the page lock only inside **`apply_semantic_page_result`**.

### Journal pages — Phase-2 semantic bypass

**Problem:** Journal-heavy vaults spend disproportionate Phase-2 time on daily fleeting notes the daemon itself appends to (`Journey Log`, task markers). Semantic summaries and block embeddings on `journals/YYYY_MM_DD.md` add LLM token and embedding cost without improving durable `pages/` knowledge.

**Policy (shipped):**

| Stage | `pages/` | `journals/` |
|-------|----------|-------------|
| Pending detection | `page_needs_phase2_cognitive` — full semantic queue rules | Same function, but returns `false` once structural ledger matches `mtime` (never semantic re-queue) |
| Duty-cycle handler | `_process_llm_cycle_file` — cognitive lint → `index_page` → `apply_semantic_page_result` → optional dual embed | `_settle_journal_structural_cycle_file` — read, link registry, AST `apply_file_event`, `FileState` processed |
| Vault progress | Counted in `phase2_cognitive_total` / `done` | **Excluded** from Phase-2 vault metrics |

**Detection:** `is_journal_page_path(graph_root, path)` — path relative to `LOGSEQ_GRAPH_PATH` has first segment `journals`.

**Non-goals:** This does **not** skip Phase-1 bootstrap catalog harvest for journals (bootstrap still walks `journals/**/*.md` for the master index). It does **not** disable Journey Log writes or MCP `append_journal`.

**Verification:** `tests/test_maintenance_daemon.py::test_run_cycle_journal_phase1_only_skips_semantic_indexing`, `test_page_needs_phase2_cognitive_journal_settles_without_semantic_requeue`.

---


## Frozen KV prefix

- `FrozenPromptPrefix` in [`page_prompt_session.py`](../../src/agent/page_prompt_session.py): SHA-256 over canonical system + stable user bytes.
- `verify_unchanged()` before each LLM call; ops log field `kv_prefix_hash`.
- Task tail uses fixed delimiter `CANONICAL_TASK_HEADER` in [`prompt_layout.py`](../../src/agent/prompt_layout.py) (no `.strip()` on stable body).

Non-LLM bootstrap paths (regex catalog hits) may sleep `MATRYCA_BOOTSTRAP_IO_BATCH_PAUSE_MS` (default 2 ms) between files to spare slow disks.

Daemon checkpoint frequency during Phase 1 is controlled by `MATRYCA_BOOTSTRAP_CHECKPOINT_EVERY` (default 50), not a hard-coded interval. Phase 1 pill history uses `MATRYCA_BOOTSTRAP_PILL_CHECKPOINT_EVERY` (default 5). Sovereign UI live telemetry uses `MATRYCA_TELEMETRY_HEARTBEAT_SECONDS` (default 5) — see [`live-telemetry-ui.md`](live-telemetry-ui.md).

---

## Operator checklist (large vaults)

1. Copy the **v1.8 Edge computing & performance** block from `.env.example`.
2. Keep `MATRYCA_PLUMBER_CONTEXT_COMPRESSION=false` unless you accept extra LLM calls that rewrite history.
3. On HDD or busy laptops: set `MATRYCA_YIELD_SLEEP_MS=1`–`5`, increase thermal delays modestly.
4. If RAM is tight: `MATRYCA_BM25_MODE=ondemand`, lower `MATRYCA_SEMANTIC_CACHE_MEMORY_ENTRIES`, set `MATRYCA_RAM_BUDGET_MB` and watch `logs/matryca_plumber_ops.log` for budget warnings.
5. Load-test locally: `uv run python scripts/gen_synthetic_graph.py /path/to/graph --count 1000` then run bootstrap; soak: `make perf`.

---

## Verification

| Test area | Location |
|-----------|----------|
| Prompt layout / harvest | `tests/test_llm_context_payload.py` |
| Tier-1 builders / hashes | `tests/test_daemon_prompts.py`, `tests/prompt_hash_snapshots.json` |
| L0 write safety | `tests/test_safety_validators.py` |
| SYSTEM_PROMPT assembly | `tests/test_build_system_prompt.py`, `make check-system-prompt` |
| PagePromptSession | `tests/test_page_prompt_session.py` |
| Semantic cache LRU | `tests/test_semantic_cache_router.py` |
| Memory teardown | `tests/test_memory_budget.py` |
| Backlink index | `tests/test_backlink_index.py` |
| Bootstrap yield | `tests/test_bootstrap_yield.py` |
| Adaptive LLM | `tests/test_llm_client_adaptive.py` |
| Resilient JSON / Gemma tail | `tests/test_json_repair.py` |
| Round 4 audit (stateless insights, catalog cap, compression sanitize, `id::`) | `tests/test_maintenance_daemon.py`, `tests/test_context_compressor.py`, `tests/test_mldoc_phase7.py` |
| CPU sandbox | `tests/test_process_priority.py` |
| Mmap reads | `tests/test_markdown_io.py` |
| Slow soak | `tests/slow/test_daemon_memory_soak.py` (`pytest -m slow`) |
| Journal Phase-2 bypass | `tests/test_maintenance_daemon.py` (`test_run_cycle_journal_phase1_only_skips_semantic_indexing`) |
