# Architecture

Pilot index for system structure. **Legacy [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) remains authoritative during Phase 1.**

## Current pilot

- [System overview](system-overview.md) — Three-surface runtime, vault topology, daemon phase model.
- [Graph plane](graph-plane.md) — Markdown SSOT, parser, OCC, locks, sandbox, `graph_dispatch`.
- [Shadow DB](shadow-db.md) — Opt-in SQLite read cache, sync, health, routing, fallback (`v2.0.0-alpha`+).
- [Cache-friendly retrieval](cache-friendly-retrieval.md) — Retrieval/context cache boundaries, deterministic output, and staged validation.

## Planned concepts

| Concept | Legacy source |
| --- | --- |
| Daemon runtime | [`docs/CLEAN_CODE_ARCHITECTURE.md`](../../CLEAN_CODE_ARCHITECTURE.md#maintenance-daemon-module-map-issue-58) |
| Sovereign UI | [`docs/openspec/live-telemetry-ui.md`](../../openspec/live-telemetry-ui.md) |
| Prompt stack | [`docs/PROMPT_ARCHITECTURE.md`](../../PROMPT_ARCHITECTURE.md) |
| Security boundaries | [`docs/openspec/security-sandbox.md`](../../openspec/security-sandbox.md) |
