## X-Ray mode and session aliases (`[n]`)

For large pages, prefer **`read_graph_data` / `target_type="xray_page"`** with `query` = page title. The tool returns an ultra-dense outline like `[0] Parent` / `  [1] Child` (properties stripped) and writes `.matryca_xray_state.json` mapping each `[n]` to the real Logseq block UUID. Normal mode keeps the established graph-root location. With `MATRYCA_READ_ONLY=true`, state is written instead to the private per-graph external runtime cache at `<cache-root>/graphs/<graph-id>/xray/`; no graph path is created or modified. The graph identity prevents cross-vault sharing, the state file is atomically replaced under a process-safe lock, POSIX directory/file modes are `0700`/`0600`, and its lifetime follows the per-graph runtime cache.

Before #393, strict read-only X-Ray parsed the requested page and only then attempted the graph-root alias write, where the shared lock/write policy raised `GraphReadOnlyError`. The external state route makes the public read classification match runtime behavior without weakening the graph boundary.

**Gate B impact decision (#393):** the published RC2 soak did not invoke `xray_page`, so its terminal receipt does not claim that probe coverage. The corrected branch is covered by the focused X-Ray generation, alias-resolution, concurrent-replacement, cross-graph-isolation, and graph-manifest tests in the stable candidate CI; no historical soak credit is retroactively assigned.

On later **`mutate_graph`** or **`refactor_blocks`** calls (including separate CLI invocations), pass **`[n]`** directly wherever you would use a 36-character UUID:

- `write_outline` / `inject_query`: `target` = `[0]` (parent block alias) **or** `Page Title|[0]` (recommended for local LLMs)
- `edit_property` / `generate_flashcards`: `target` or `target_uuid` = `Page Title|[1]`
- Unknown alias **without** page context → `ok: false` — re-run `xray_page` on that page to refresh the map
- **v1.9.7+ safe fallback:** `Page Title|bad-uuid` on an existing page → outline appended at page bottom; response includes `warnings` — read them before continuing

Use `target_type="page"` when you need full spatial metadata (`synthetic_id`, `source_uuid`, properties). Use **`xray_page`** when you only need topology + text and minimal tokens.

---
