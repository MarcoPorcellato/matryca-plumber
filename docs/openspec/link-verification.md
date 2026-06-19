# Structural link verification (v1.9 — GitHub #15)

**Milestone:** v1.9.0 — Structural Graph Hygiene  
**Implementation:** [`src/graph/link_verification.py`](../../src/graph/link_verification.py)  
**Daemon hook:** [`MaintenanceDaemon._finalize_link_and_journey_pass`](../../src/agent/maintenance_daemon.py)

Zero-LLM hygiene for **external URL rot** and **missing local assets**. The graph remains the system of record; a JSON sidecar is only an ephemeral verification queue (TRIZ *Intermediary*).

---

## Problem

Large Logseq vaults accumulate:

- Dead `http(s)://` links (404, DNS failure, TLS errors)
- Broken `assets/` references after files are moved or deleted

Manual auditing does not scale. Synchronous HTTP on the daemon main thread would block the duty cycle and stress CPU-only hosts.

---

## Pipeline (three phases)

```mermaid
flowchart TB
  subgraph extract [1. Extract — passive]
    P1[Page read during duty cycle]
    RX[Regex: URLs + image/asset paths]
    REG[".matryca_link_registry.json"]
    P1 --> RX --> REG
  end

  subgraph verify [2. Verify — async batch]
    BATCH[Up to MATRYCA_LINK_VERIFY_BATCH entries]
    HEAD[httpx HEAD for URLs]
    FS[Path.is_file for assets]
    BATCH --> HEAD
    BATCH --> FS
  end

  subgraph flag [3. Flag — OCC write]
    STRIKES["strikes >= MATRYCA_LINK_VERIFY_STRIKES"]
    OCC[occ_snapshot + page_rmw_lock]
    PROP["dead-link:: true or missing-asset:: true"]
    STRIKES --> OCC --> PROP
  end

  REG --> BATCH
  HEAD --> STRIKES
  FS --> STRIKES
```

| Phase | When | Work |
|-------|------|------|
| **Extract** | Whenever the daemon reads page bytes (fast-track skip path or LLM cycle) | Anchor each URL/asset to `page_relpath` + `block_uuid` |
| **Verify** | End of each duty cycle (`_finalize_link_and_journey_pass`) | Async batch; no LLM |
| **Flag** | After repeated failures (default **2** cycles) | Append block property under the anchored bullet |

Protected lines (fenced code, queries) are excluded via `compute_page_protected_line_indices`.

---

## Sidecar schema

**Path:** `{LOGSEQ_GRAPH_PATH}/.matryca_link_registry.json`  
**Locking:** `cross_process_json_flock` on load and save (same family as daemon state)  
**Persistence (v1.10.0 — #41):** `_save_registry_unlocked` writes via `atomic_write_bytes` (temp → `fsync` → `os.replace`) so a crash mid-write cannot leave truncated JSON. Merge-on-save in `_persist_checked_registry_updates` reloads fresh entries under flock before applying verification deltas.

```json
{
  "version": 1,
  "updated_at": "2026-06-01T12:00:00+00:00",
  "entries": {
    "pages/demo.md|uuid|url|https://example.com/dead": {
      "kind": "url",
      "target": "https://example.com/dead",
      "page_relpath": "pages/demo.md",
      "block_uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "strikes": 2,
      "last_status": 404,
      "last_checked_at": "...",
      "flagged": true
    }
  }
}
```

Registry keys are deterministic: `{page_relpath}|{block_uuid}|{kind}|{target}`.

**v1.9.9 sandbox (Security & Sandbox milestone):** Before any asset or registry-backed read, `link_verification` validates `page_relpath` and resolved asset paths with `path_sandbox`. Tampered registry rows and traversal refs (`../`, symlink escape) are treated as missing — no bytes read outside `LOGSEQ_GRAPH_PATH`. Spec: [`security-sandbox.md`](security-sandbox.md).

---

## On-graph result (AST parity)

Properties are inserted at the correct **+2 indent** under the parent bullet (same rules as `matryca-plumber::` stamping):

```markdown
- Check out this article: https://example.com/dead-page
  dead-link:: true
  id:: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
- ![diagram](../assets/missing.png)
  missing-asset:: true
  id:: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb
```

Writes use `atomic_write_bytes_if_unchanged` with Phase-1 `baseline_mtime` (`st_mtime_ns`, integer) — identical OCC contract as cognitive lint ([`ARCHITECTURE.md`](../ARCHITECTURE.md#optimistic-concurrency-control-occ)).

---

## Environment variables

| Variable | Default | Role |
|----------|---------|------|
| `MATRYCA_LINK_VERIFY_ENABLED` | `true` | Master switch |
| `MATRYCA_LINK_VERIFY_STRIKES` | `2` | Failed checks before flagging |
| `MATRYCA_LINK_VERIFY_BATCH` | `25` | Max verifications per duty cycle |
| `MATRYCA_LINK_VERIFY_TIMEOUT` | `8` | HTTP HEAD timeout (seconds) |

Documented in [`.env.example`](../../.env.example) (Operator essentials).

---

## Alternatives rejected (issue #15)

| Approach | Why not Plumber |
|----------|-----------------|
| Semantic / LLM quote hashing | CPU + RAM cost on 16 GB hosts; better suited to Matryca Brain tier |
| Synchronous GET/HEAD on main thread | Blocks duty cycle and Sovereign UI responsiveness |
| Auxiliary SQL/Redis store | Violates local-first Markdown-only system of record |

**Prior art:** claims-sidecar pattern ([issue #14](https://github.com/MarcoPorcellato/matryca-plumber/issues/14), [gist](https://gist.github.com/kiluazen/727948f9517eacd665d21199e8318da1)).

---

## Operator notes

- Network blips can increment `strikes`; the threshold reduces false positives. Flagged entries are re-checked each cycle; recovery clears strikes, registry `flagged`, and on-graph hygiene properties.
- HEAD may return 405/403; the verifier falls back to GET for inconclusive HEAD responses.
- When [`agent-dx.md`](agent-dx.md) journey logging is enabled (`MATRYCA_JOURNEY_LOG_ENABLED=true`), link-check totals roll into the single `- 🤖 Matryca Activity` bullet in today's journal (cumulative `links_checked` / flagged counts via `DaemonState.journey_day`).
- Disable entirely: `MATRYCA_LINK_VERIFY_ENABLED=false`.
