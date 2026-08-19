---
type: Document
---
## Formatting discipline (non-negotiable)

These rules mirror Logseq OG's Clojure/Datalog on-disk contract. Violations cause silent index corruption — not immediate parse errors.

1. **Two property planes** — page frontmatter (no bullet) vs block properties (+2 indent under bullet). Never prefix page `tags::` with `- `.
2. **Property placement** — block properties MUST sit directly under the bullet text, before children or multiline continuations. Never orphan or delete existing `id::` lines.
3. **Multiline padding** — Shift+Enter continuations use `indent + 2 spaces`; preserve Windows `\r\n` or Unix `\n` line endings when editing — Matryca normalizes reads but you must not strip `\r` manually mid-block.
4. **Namespace filenames** — semantic `Domain/Topic` → on-disk `Domain___Topic.md` with percent-encoding for reserved OS chars; never hand-craft filenames with raw `/`. **v1.9.7+:** pass semantic titles to tools — Plumber normalizes `___`, `.md`, and casing (`page_input_normalizer.py`). Path traversal (`../`) is rejected.
5. **UTF-8 only** — all graph I/O is `encoding="utf-8"`.
6. **Dead zones** — never mutate lines inside fenced code blocks, HTML comments, or `#+BEGIN_QUERY` … `#+END_QUERY` regions.
7. **Sandbox boundary** — never supply paths outside `LOGSEQ_GRAPH_PATH` or L1 `$HOME` scope; traversal attempts are rejected fatally.

When in doubt: `read_graph_data` / `target_type="page"` first, then `dry_run: true` on every mutator.
