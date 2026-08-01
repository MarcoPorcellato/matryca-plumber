# Security & Sandbox (v1.9.9)

**Milestone:** v1.9.9 — Security & Sandbox (v1.9.x perfection track)  
**Implementation:** [`src/graph/path_sandbox.py`](../../src/graph/path_sandbox.py), [`src/utils/bounded_json.py`](../../src/utils/bounded_json.py), [`scripts/check_graph_read_sandbox.py`](../../scripts/check_graph_read_sandbox.py)  
**Operator matrix:** [`SECURITY.md`](../../SECURITY.md)

v1.9.9 closes the pre-v2.0 **Security & Sandbox** milestone: every graph-local read path is sandbox-validated, JSON checkpoints are size-bounded, and CI blocks new `Path.read_text()` bypasses in graph/agent/rag code.

---

## Path sandbox (reads and writes)

All candidate paths under `LOGSEQ_GRAPH_PATH` are resolved with `Path.resolve()` and checked with **`is_relative_to(graph_root)`** before I/O.

| Primitive | Role |
|-----------|------|
| `assert_path_within_graph` | Raises `PathTraversalSecurityError` on escape |
| `read_graph_file_text` | Read UTF-8 only after sandbox pass |
| `read_graph_page_text` | Sandbox + optional mmap (`markdown_io.py`) |
| `resolve_graph_relative_key` | Map registry keys back under the graph root |

**v1.9.9 hardening:**

- **Link verification** — `_resolve_asset_path` and `.matryca_link_registry.json` `page_relpath` values are validated before read; traversal refs and tampered registry rows are treated as missing/invalid ([`link-verification.md`](link-verification.md)).
- **wiki_lint** — `is_scannable_graph_markdown()` skips symlink escape under flat `pages/*.md`.
- **Defense-in-depth** — graph/agent/rag modules use `read_graph_file_text()` instead of raw `Path.read_text()`; `make sandbox-read-check` enforces this in CI.

---

## Runtime write policy

`RuntimeWritePolicy` in [`src/graph/safety/write_policy.py`](../../src/graph/safety/write_policy.py) is the fail-closed contract for graph-root mutations.

| Variable | Behavior |
|----------|----------|
| `MATRYCA_READ_ONLY` | Default `false`. When `true`, any candidate write path whose canonical resolution lies under the canonical graph root raises `GraphReadOnlyError(code="graph_read_only")`. |
| `MATRYCA_CACHE_PATH` | Optional external cache root. The path is canonicalized before use; symlink aliases, relative targets, and unresolved targets fail closed. The resolved cache root must stay outside the graph root or the policy rejects it. |

The policy resolves both graph and cache roots canonically, so symlink aliases into the graph are treated the same as direct descendants. `MATRYCA_CACHE_PATH` is always treated as an external cache root, not a graph-local working directory. This contract exists before enforcement at callers, CLI, MCP, Shadow, or daemon entry points.

---

## Bounded JSON checkpoints

Graph-local JSON files (catalog, link registry, daemon state, semantic cache, block vectors) load through **`read_bounded_json()`** with env **`MATRYCA_JSON_MAX_BYTES`** (default **64 MiB**). Oversized files fail fast instead of causing local memory DoS.

---

## JSON flock and atomic persistence (v1.10.0)

Beyond size bounds, hot sidecars use **`cross_process_json_flock`** so readers never observe torn JSON during concurrent `atomic_write_bytes` replace, and writers merge or atomically commit:

| File | v1.10.0 behavior |
|------|------------------|
| `.matryca_semantic_cache/master_catalog.json` | Load + backup refresh under flock ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35)); `save()` merge-on-save by `last_mtime` ([#36](https://github.com/MarcoPorcellato/matryca-plumber/issues/36)) |
| `.matryca_link_registry.json` | Save via `atomic_write_bytes` ([#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)) |
| `.matryca_daemon_state.json` | Already flock + atomic replace (pre-existing) |

Bootstrap harvest skips catalog upsert when semantic index append OCC-aborts ([#37](https://github.com/MarcoPorcellato/matryca-plumber/issues/37)) so catalog rows cannot claim summaries absent from page bodies.

**v1.10.3 sidecar permissions:** flock sidecar files (`*.flock`, page RMW locks, daemon process lock) are created with mode **`0o600`** so other OS users cannot read lock metadata on shared hosts.

See [`runtime-bootstrap.md`](runtime-bootstrap.md#master-catalog-persistence-v1100) and [`ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## Debug log and UI token policy

| Variable | v1.9.9 behavior |
|----------|-----------------|
| `MATRYCA_LLM_DEBUG_LOG_PATH` | Must lie under allowed roots (`config_paths`); secrets redacted in NDJSON when log redaction is on |
| `MATRYCA_UI_REQUIRE_EXPLICIT_TOKEN` | `.env.example` **template** is `true` — new installs must set `MATRYCA_UI_TOKEN`; runtime default when unset remains permissive for legacy `.env` files |

Ephemeral auto-generated UI tokens are still exposed on loopback via `/api/auth/session`; set an explicit token on shared hosts.

---

## Contributor gate

```bash
make sandbox-read-check   # scripts/check_graph_read_sandbox.py
make ci                   # format-check + lint + typecheck + sandbox-read-check + test (GitHub Actions)
```

New graph reads in `src/graph/`, `src/agent/`, `src/rag/`, or `src/semantic/` must go through `read_graph_file_text()` / `read_graph_page_text()` unless allowlisted in the check script.

**Allowlisted exceptions (not graph markdown):**

| File | Rule |
|------|------|
| `src/graph/path_sandbox.py`, `src/graph/markdown_io.py` | Sandbox primitives |
| `src/agent/maintenance_daemon.py` | Only pid/lock sidecar reads tagged `# sandbox-read-ok` on the same line as `.read_text()` |
| `src/utils/bounded_json.py`, `src/utils/config_paths.py`, … | Non-vault config I/O (see script `ALLOWLIST`) |

Do **not** add new `# sandbox-read-ok` markers for graph `pages/` or `journals/` markdown — use `read_graph_file_text()` instead.

---

## Related specs

- [`link-verification.md`](link-verification.md) — extract/verify/flag pipeline
- [`agent-ax-robustness.md`](agent-ax-robustness.md) — MCP page-title normalization (complements sandbox rejects)
- [`agent-onboarding.md`](agent-onboarding.md) — `llms.txt` §2.4 operator summary
