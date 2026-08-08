# Runtime bootstrap (startup provisioning)

**Roadmap:** [`ROADMAP_LLM_WIKI.md`](../../ROADMAP_LLM_WIKI.md) (L1/L2, `matryca-wiki.yml`)

Matryca Plumber provisions **directories and optional config files** before harvest, lint, or daemon duty cycles touch the vault. Provisioning is **idempotent**: existing files are never overwritten.

**Implementation:** `src/utils/runtime_bootstrap.py` (`prepare_matryca_runtime`, `try_prepare_matryca_runtime_from_env`).

---

## When bootstrap runs

| Entry surface | Trigger |
|---------------|---------|
| **Maintenance daemon** | `start_daemon_foreground` and `MaintenanceDaemon.run_forever` (before bootstrap harvest) — **eager** AST |
| **MCP stdio** | `app_lifespan` in `src/main.py` — **light** bootstrap (`eager_graph=False`); AST on first graph tool call |
| **Agent CLI** (`read`, `search`, …) | `cli.main` via `try_prepare_matryca_runtime_from_env()` — **eager** AST |
| **Sovereign UI** | `matryca plumber status` / `ui` → FastAPI lifespan (`eager_graph=False`); also `POST /api/config`, graph-path save, `POST /api/provision-l1`, `POST /api/daemon/start`, and L1 pre-flight check — all **lazy** (`eager_graph=False`, v1.9.11) |

`matryca plumber status` / `ui` does **not** run eager bootstrap in `cli.main` (UI lifespan handles light provisioning). `matryca plumber start` does **not** start the UI.

When a valid graph is configured, **daemon and agent CLI** **bootstrap the in-memory `LogseqGraph` cache** eagerly and load **Telos / AI Constraints** from the identity config page if present ([`identity-config.md`](identity-config.md)). **MCP stdio** and the **Sovereign UI** defer AST parsing until the first graph read (lazy load) so handshakes, `:8500` bind, settings save, and **Start Engine** return in seconds on large vaults (v1.9.11); the spawned daemon subprocess still bootstraps eagerly. See [`../integrations/hermes-agent.md`](../integrations/hermes-agent.md).

If `LOGSEQ_GRAPH_PATH` is unset or invalid, only **log directories** are ensured.

With `MATRYCA_READ_ONLY=true`, every entry surface still runs the light runtime
bootstrap, but graph-local provisioning, AST/identity refresh, write-back hooks, and
sidecar maintenance are skipped. A configured graph-local ops or Loguru path is
redirected to the validated external per-graph runtime cache before any directory is
created; explicitly external log paths keep their configured locations. When Shadow is enabled, startup may read
`pages/` and `journals/` and create or reconcile only the validated external Shadow
cache. Explicit Shadow-off remains zero-touch for that cache.

On first startup, if repo **`.env`** is missing and **`.env.example`** exists, Matryca Plumber copies the example to `.env` (logged at INFO) before loading environment variables.

---

## What is provisioned

### 1. Log sinks (always)

| Artifact | Env override | Default |
|----------|--------------|---------|
| Ops JSONL (token-accurate LLM trace) | `MATRYCA_PLUMBER_LOG_PATH` | `logs/matryca_plumber_ops.log` (under repo root) |
| Rotating application log (Loguru) | `MATRYCA_LOGURU_LOG_PATH` | `logs/matryca_plumber.log` |

**Rationale:** Parent directories are created with `mkdir(parents=True, exist_ok=True)` so the Sovereign UI activity feed and Loguru rotation never fail on first write. Paths must resolve under allowed roots (`$HOME`, repo, temp) — see `src/utils/config_paths.py`.

`configure_loguru()` delegates to the same helper so file sinks and bootstrap stay aligned.

**Gate B impact decision (#388):** the published `2.0.0rc1`
`read-only-external` profile uses an external cache and does not configure graph-local
log overrides, so it cannot enter the corrected redirection branch. Existing Gate B
credit remains evidence for the exact RC artifact and is not rewritten. A stable
candidate that includes this fix must pass the focused MCP, CLI, UI, and daemon startup
matrix with both graph-local and external log settings, including an unchanged
byte-and-metadata graph manifest; the historical multi-day RC soak does not need to be
restarted for this configuration-excluded branch.

### 2. L1 memory (when a valid graph is configured)

| Artifact | Default location | Overrides |
|----------|------------------|-----------|
| L1 directory | `<parent-of-LOGSEQ_GRAPH_PATH>/matryca-l1/` | `MATRYCA_L1_PATH`, or `memory_path` in `matryca-wiki.yml` |
| `README.md` | Inside L1 dir | Created only if missing — **not** loaded into LLM context |
| `session-rules.md` | Inside L1 dir | Created only when no other content `*.md` exists (excluding `README.md`) |

**Why L1 is a sibling of the vault (default):**

1. **L1 ≠ L2** — Session rules, deploy notes, and identity stubs are not part of the wiki corpus indexed as Logseq pages.
2. **Scan isolation** — The daemon harvests `pages/` and `journals/` only; a sibling folder is never ingested as graph content.
3. **Multi-vault sharing** — Several vaults under the same parent directory can share one L1 folder.
4. **Operational separation** — Sync/backup of the vault does not have to include agent-local rules unless you choose to.

To keep L1 **inside** the graph root instead, set:

```env
MATRYCA_L1_PATH=/absolute/path/to/your/vault/matryca-l1
```

or `memory_path` in `matryca-wiki.yml`. Bootstrap will create that path and seed `matryca-wiki.yml` accordingly.

**L1 read safety:** `collect_l1_markdown_paths` only reads under `$HOME` or the system temp directory. `README.md` is excluded from agent context by filename (documentation only).

### 3. Graph-local working directories (when a valid graph is configured)

These artifacts are provisioned only when graph writes are allowed. Strict Read Only
does not create, repair, lock, rename, or remove any path inside the graph.

| Directory / file | Purpose |
|------------------|---------|
| `.matryca_semantic_cache/` | Working cache root — excluded from alias/catalog page scans |
| `.matryca_semantic_cache/master_catalog.json` | Phase 1 catalog rows (summaries, tags, mtimes) |
| `.matryca_semantic_cache/backlink_counts.json` | Persisted incoming wikilink counts (v1.8 — avoids full-graph rescans) |
| `.matryca_semantic_cache/semantic_clusters.json` | Louvain neighborhoods for Phase 2 cluster cycles |
| `.matryca_semantic_cache/*.json` (hash names) | Per-operation semantic inference cache (TTL); **not** deleted when reserved files above are present |
| `.matryca_link_registry.json` | Ephemeral link/asset verification queue (v1.9 — not a system of record; see [`link-verification.md`](link-verification.md)) |
| `templates/` (or `templates_subdir` from wiki YAML) | Template Markdown for `read_logseq_template` |

**Rationale:** Cache and templates must exist before the first catalog save or template read; creating them at startup avoids racey `mkdir` scattered through writers.

`MATRYCA_CACHE_PATH` is always an external cache root. The policy canonicalizes graph and cache roots and rejects relative, unresolved, or symlink-alias paths that cannot be proven outside the graph root.

### 4. Wiki orchestration file (when missing)

| File | Behavior |
|------|----------|
| `<graph-root>/matryca-wiki.yml` | Copied from `matryca-wiki.example.yml` in the repo if absent; `memory_path` is patched to the resolved L1 directory |

**Rationale:** Namespaces, `wiki_file_prefix`, and structural-hop limits are orchestration metadata — not Logseq page content. Seeding gives new graphs a sane default without manual copy-paste.

---

## What is *not* provisioned at bootstrap

| Artifact | Reason |
|----------|--------|
| Repo **`.env`** (pre-existing) | Never overwritten; auto-created from `.env.example` only when `.env` is absent |
| **`pages/` / `journals/`** | A valid Logseq graph must already exist; Matryca Plumber does not fabricate vault structure |
| **`.matryca_daemon_state.json`**, **`.matryca_xray_state.json`** | Runtime ledgers — created on first checkpoint / X-Ray session |
| **Daemon PID / lock files** | PID sidecar written immediately after `.matryca_plumber_daemon.lock` acquisition in `start_daemon_foreground`; removed on bootstrap failure or `SIGINT`/`SIGTERM` during startup |
| **`master_catalog.json` body** | Populated by bootstrap harvest, not empty placeholders |
| **`.matryca_link_registry.json`** | Created on first link extract (v1.9); verification queue only — see [`link-verification.md`](link-verification.md) |

This follows *create on first meaningful write* for stateful JSON so checkpoints stay honest.

---

## Master catalog persistence (v1.10.0)

**File:** `.matryca_semantic_cache/master_catalog.json`  
**Module:** [`src/graph/master_catalog.py`](../../src/graph/master_catalog.py)

| Operation | Contract |
|-----------|----------|
| **Load** | `load_master_catalog` / `_load_catalog_payload_from_disk` read under `cross_process_json_flock` ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35)); `.bak` restore and quarantine also under flock |
| **Save (default)** | `MasterCatalog.save()` reloads disk rows under flock and **merge-on-save** by `last_mtime` ([#36](https://github.com/MarcoPorcellato/matryca-plumber/issues/36)) — daemon Phase-2 sync, harvest CLI, and graceful shutdown no longer clobber concurrent writers |
| **Save (prune)** | `save(replace=True)` after `prune_missing_pages()` — intentional full replace of stale ghost rows |
| **Remove during harvest** | `catalog.remove()` queues `_pending_removals` applied on next merge save |

**Bootstrap harvest (#37):** After LLM inference, `_append_minimal_semantic_index` returns `bool`. Catalog upsert runs only when the semantic index block was written (or header already present). OCC abort → `pending_llm` status, no catalog/page drift; page retries on next incremental harvest.

**Operator invariant:** Tier-2 agents read the compiled **`[[Matryca Master Index]]`** page — not the JSON file directly ([`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md)).

---

## Related specs

- [`l1-l2-routing.md`](l1-l2-routing.md) — How L1 content is loaded into agent context vs L2 graph reads.
- [`identity-config.md`](identity-config.md) — In-graph Telos / AI Constraints and `store_fact`.
- [`ingest.md`](ingest.md) — `ingest_document` (ingest / `LOG` / `GLOSSARY` pages created on first use, not at bootstrap).
- [`llm-performance.md`](llm-performance.md) — v1.8 KV-cache layout, memory teardown, cooperative harvest.
- [`link-verification.md`](link-verification.md) — v1.9 link registry and hygiene properties.
- [`agent-dx.md`](agent-dx.md) — v1.9 CLI JSON, context macro, Journey Log (cumulative daily bullet).
- [`agent-onboarding.md`](agent-onboarding.md) — v1.9.2 `llms.txt` / PyPI `uvx` agent contract.
- [`live-telemetry-ui.md`](live-telemetry-ui.md) — v1.9.3 Sovereign UI telemetry heartbeat env vars.
