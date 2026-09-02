# Architecture

Progressive-disclosure index for maintained system concepts. [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) remains the detailed architecture contract.

## Maintained concepts

- [System overview](system-overview.md) — Three-surface runtime, vault topology, daemon phase model.
- [Graph plane](graph-plane.md) — Markdown SSOT, parser, OCC, locks, sandbox, `graph_dispatch`.
- [Shadow DB](shadow-db.md) — Opt-in SQLite read cache, sync, health, routing, fallback (`v2.0.0-alpha`+).
- [Cache-friendly retrieval](cache-friendly-retrieval.md) — Retrieval/context cache boundaries, deterministic output, and staged validation.
- [BM25 query-cache capacity](bm25-query-cache-capacity.md) — Reproducible capacity, latency, RSS, churn, and parity decision for the 8,192-entry default.
- [LLM-free information-cluster recognition](llm-free-cluster-recognition.md) — Deterministic feature generations, clustering quality, invalidation, and reuse across related-note functions.
- [Epistemic memory landscape and standard direction](epistemic-memory.md) — Draft research direction for provenance-bound, human-governed claims and a future interoperable contract; no runtime feature or standard claim.

## Planned concepts

| Concept | Legacy source |
| --- | --- |
| Daemon runtime | [`docs/CLEAN_CODE_ARCHITECTURE.md`](../../CLEAN_CODE_ARCHITECTURE.md#maintenance-daemon-module-map-issue-58) |
| Sovereign UI | [`docs/openspec/live-telemetry-ui.md`](../../openspec/live-telemetry-ui.md) |
| Prompt stack | [`docs/PROMPT_ARCHITECTURE.md`](../../PROMPT_ARCHITECTURE.md) |
| Security boundaries | [`docs/openspec/security-sandbox.md`](../../openspec/security-sandbox.md) |
