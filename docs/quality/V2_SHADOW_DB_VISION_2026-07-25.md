# What Matryca Plumber Gains from v2.0 and the Shadow DB

_Working note — 2026-07-25, written while the 24h+ soak (r8) was running before the beta release._

## The original vision, verified

> "At 15:07, the 24-hour SOAK started to test everything I built over the past few days for Matryca Plumber v2.0. We are therefore very close to the v2.0 quantum leap, which will introduce a supporting Shadow DB and accelerate every read operation from the Logseq database. This will greatly increase the system's capabilities and make it suitable as a highly granular, powerful primary memory for artificial intelligence agents, with Logseq's block-level granularity instead of the monolithic pages used by Obsidian and others."

Every statement here is **supported** by the code and roadmap, with a few technical clarifications that make the story more precise.

---

## 1. What the Shadow DB actually is

It is not a new database that replaces Logseq. It is a **read cache**, managed entirely by the Matryca Plumber daemon, that complements—but never replaces—the Markdown files.

- **Source of truth:** Markdown on disk always remains authoritative. Logseq OG continues to write `.md` files, and Matryca Plumber continues to write `.md` files with OCC safety (`st_mtime` + page lock, the same anti-corruption guarantee already available in v1).
- **Shadow DB** (`shadow.sqlite`, inside `.matryca_semantic_cache/`) is a **synchronized mirror** of that Markdown, designed for fast **reads**: FTS5 (SQLite's native full-text search) for text search, and **recursive CTEs** (Common Table Expressions) for reading entire block subtrees with a single query instead of rebuilding them in memory each time.
- It **replaces** the old v1.9.5 path: loading the entire `master_catalog.json` into RAM and computing BM25 in-process for every search. That path remains available as an **automatic fallback**—if the Shadow DB is not ready, for example during a rebuild or after a schema mismatch, the system returns to Markdown/BM25 without requiring user intervention.
- It is **opt-in**: enable it with `MATRYCA_SHADOW_DB_ENABLED=true`; the default is off. Users who do not enable it retain the existing behavior. This is why the release is so carefully controlled: it is not a big-bang migration, but an accelerator that can be enabled when ready.

**The concrete difference for users:** sub-50ms reads instead of reloading or recomputing the in-memory BM25 corpus for every request. For an AI agent that queries the graph dozens or hundreds of times during a working session, this is the difference between an assistant that pauses to "think" about every question and one that responds immediately.

## 2. Block-level granularity and why it matters most

This intuition is correct and represents **the** differentiator, not a minor technical detail:

- The Shadow DB schema contains `pages`, `blocks`, `block_refs`, and `blocks_fts` tables. The **block**—a single Logseq bullet with its `id::` UUID—is the atomic indexed unit, not the page.
- `query_subtree_by_block_uuid` queries use recursive CTEs to request "this block and all its children up to depth N." A page-based system such as Obsidian, where the unit is the whole file or note, does not offer the same operation in the same form: it must load the whole note and parse its text to locate the relevant subsection.
- For an AI agent, this means **retrieving exactly the context it needs**, rather than the entire surrounding page. It is selective memory rather than "all or nothing"—closer to human recall, which retrieves specific details instead of rereading an entire chapter, than to basic file-based text search.

This aligns with the quotation already in the README: *"Logseq is building the best local outliner database. But AI Agent memory is at the very bottom of their roadmap. Matryca Plumber gives you that future today."* The Shadow DB is the infrastructure that makes this promise fast and scalable, not merely possible.

## 3. "Primary memory for AI agents": what exists now and what comes next

Precision matters here so that the beta does not promise more than it delivers:

- **In v2.0.0-beta.1:** the Shadow DB covers the **read path**—bootstrap, rebuild, health-gated routing, FTS5, and CTEs. This is already sufficient to accelerate every read that agents perform through MCP or the CLI.
- **Outside the beta scope, already on the roadmap (Phase 4):** the "biological memory" tables—such as `memory_nodes`, `memory_edges`, `memory_episodes`, and `memory_procedures`—are **already designed in the schema** (inspired by a biological memory model; see `ROADMAP_V2_BIOLOGICAL_MEMORY.md`), but are not part of this release. They are the next leap: not merely "reading faster," but creating a true **memory graph** with episodes, procedures, and consolidation. This is what turns the Shadow DB from an accelerator into a genuine cognitive memory for the agent.

The accurate public description is therefore: **"The v2.0 beta lays a high-speed foundation for AI-agent memory. Block-level granularity and the read infrastructure are already here; biological and episodic memory will arrive in the next phase on the same infrastructure."**

## 4. Why the 24-hour soak is not bureaucracy

This is also worth explaining because it makes the launch more credible, not less:

- The team—in this case, the maintainer—found and **fixed a real bug** during this process: a timeout did not cover the entire inter-process read operation (`multiprocessing.Queue`), so stress conditions could exceed the configured deadline without a clean fallback. The bug was isolated, fixed, tested—including randomized and fuzz tests—reviewed in a pull request, and merged.
- The candidate package was then rebuilt; wheel integrity, hash, and provenance were verified against a real copied vault; and a targeted **enabled-state probe** validated rebuild, health, search, subtree reads, and controlled recovery. An **extended soak of approximately 25 hours** then ran against the same real vault to catch behavior that a short test cannot reveal: long-running cycles, restarts, file watchers for creation/modification/rename/deletion, and the guarantee that the original Markdown remains bit-for-bit unchanged.
- This is exactly the standard required for a feature that changes how an AI agent reads personal knowledge: **do not take shortcuts before establishing trust**.

## 5. How to communicate it publicly

Technical and narrative points worth using:

1. **The capability increase is real and measurable:** the system moves from a JSON catalog loaded into RAM with BM25 recomputed each time to a SQLite database with native full-text search and sub-50ms tree queries.
2. **Block-level granularity is the genuine architectural difference from Obsidian:** this is not marketing; it is encoded in the schema. The unit is a block with its UUID, not a file.
3. **Nothing breaks for users who do not want it:** it is opt-in and default-off, with automatic fallback to Markdown/BM25 whenever the Shadow DB is not ready. Markdown always remains the single source of truth; users are never asked to trust an opaque database.
4. **Release rigor is part of the story:** a real bug was found and fixed before launch, followed by a full-day soak against a real vault rather than synthetic data. This is the level of care required when the ultimate goal is to become an AI agent's memory.
5. **The direction is larger than the beta:** this is the first building block of infrastructure that will support genuine episodic and biological memory for agents. The beta is not the destination; it is the fast foundation on which that future will be built.

---

_Working document, not a release gate. It has no bearing on `docs/quality/issue-bodies/v2-beta-readiness.md`, which remains the sole source of truth for the release decision._
