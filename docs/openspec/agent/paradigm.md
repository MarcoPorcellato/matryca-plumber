---
type: Document
---
## Project context

Matryca Plumber operates on **Logseq OG**: local pure Markdown graphs. The atomic unit is the **block** (indented bullet tree), not a flat document body.

## Outliner rules (non-negotiable)

- Produce **hierarchical outliner text** (nested bullets).
- AI-generated sections use `- ### Heading Title` (bulleted headings) for Logseq foldability.
- Humans and the daemon edit the **same** `.md` files concurrently — preserve indentation, block order, and `id::` lines.

## Properties

### Block properties

- Immediately after bullet text, before children.
- Indented **exactly +2 spaces** relative to the parent bullet (`id::`, `matryca-plumber:: true`, etc.).
- Never orphan or delete existing block properties.

### Page properties (frontmatter)

- **Absolute frontmatter** at file top (line 0 region).
- Raw `key:: value` lines **without** leading `- ` bullet.
- Blank line before the first outliner bullet.
- `alias::` and `tags::` are comma-separated; no duplicate keys; strip `#` and `[[ ]]` from values.

## File system and namespaces

- **Semantic:** `[[Domain/Subdomain]]` in content.
- **On disk:** `/` → `___`; URL-encode reserved OS characters (`?` → `%3F`).
- **Encoding:** UTF-8 only (`encoding="utf-8"`).

## Related reading

- [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) — runtime formatting discipline
- [`docs/openspec/lint.md`](lint.md) — on-disk lint contracts

## Paradigm: blocks and outlines

- **Atomic unit:** the bullet (`- `), not the page paragraph.
- **Hierarchy:** indentation = parent/child semantics.
- **Page properties (frontmatter):** `key:: value` lines at the **absolute top of the file (line 0 region)** — **without** a leading bullet dash. Blank line before the first outliner bullet. Examples: `tags::`, `alias::`, `made-by:: matryca plumber v<installed-version>`.
- **Block properties:** `key:: value` **immediately after the parent bullet text**, indented **exactly +2 spaces** relative to the bullet, **before** continuation lines or child bullets. Examples: `id::`, `source::`, `matryca-plumber:: true`.
- **Multiline blocks (Shift+Enter):** continuation body lines inside one logical bullet must be padded to **`bullet_indent + 2 spaces`**. Only the first line has `- `. Never insert child bullets or orphan properties between continuation lines — this breaks Datalog indexing.
- **Targetability:** durable anchors need `id:: <uuid>` on disk.
- **Provenance:** attach `source::` to factual leaf blocks; Plumber-spawned pages carry `made-by::`.
- **Transclusion:** prefer `((uuid))` / `{{embed ((uuid))}}` over duplicating bodies.
- **Foldable headings:** use `- ### Section Title` (bulleted heading), not bare `###` in document body.

### `OutlineNode` (for `mutate_graph` / `action=write_outline`)

JSON tree: `text`, optional `properties`, nested `children`. Optional schema fields merge into Logseq properties:

- `page_type` → `type::` (`entity` | `project` | `knowledge` | `hub` | `feedback`)
- `domain` → `domain::` (required when `page_type` is `knowledge`: `tech` | `business` | `content` | `ops`)
- `entity_type` → `entity-type::` (required when `page_type` is `entity`: `person` | `client` | `tool` | `service` | `technology`)

Classify only blocks you intentionally tag; children usually omit schema fields.

**`heading_level` (v1.9.6+):** Local models may send `heading_level` as an integer in JSON. Plumber coerces it to a string and **never** writes `heading_level::` to disk — do not rely on that property in persisted blocks.
