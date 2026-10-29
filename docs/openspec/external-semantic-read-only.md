---
type: Document
---
# External semantic index for read-only graphs

The external semantic backend adds content-only vector search for a graph that
Plumber mounts read-only. It is separate from the legacy dual-vector cache and
from the Shadow database. The MCP tool allowlist does not change: clients use
`search_graph` with `method=semantic`.

## Experimental status and compatibility

This branch is an experimental snapshot based on commit
`905a6c6a57ca9173becc9b8df78d2051557abcd7`. It does not include subsequent
changes on the main branch and is not a release. Integration with newer source
versions requires a compatibility review and the project's checks.

The backend was backported to an installed 2.0.0 environment and locally
validated on 2026-10-26 with a BGE-M3 embedding endpoint, including snapshot
building and semantic retrieval through MCP. This evidence applies to that
configuration and does not establish compatibility with every model, server,
operating system, or deployment. Operators must qualify their own endpoint
and snapshot before use.

## Data and write boundaries

The explicit maintenance command reads graph pages through the bounded parser,
retains each Logseq block as the reference unit, and writes resumable work plus
a published SQLite snapshot under the configured external cache root. It never
writes inside the graph. Readers open only a complete published snapshot using
SQLite read-only, immutable mode; status and search do
not initialize, migrate, or create cache files. Search rechecks source hashes and
omits chunks whose source page changed or disappeared.

The external cache contains note-derived chunks, identifiers, citations, and
vectors, so protect it with permissions appropriate for graph-derived data. Build
progress and status output contain counts and error codes, not note text.

A short block remains one fragment when its complete embedding input fits. Long
blocks split preferentially into sentence or paragraph groups; code prefers line
boundaries. Oversized individual sentences or words use an explicit fallback.
Fragments never merge independent blocks. Each stores exact character offsets
within the parsed block, a block-content hash, source-page hash, original properties,
parent and ancestor references, chunk ordinal and final token count. Persisted UUIDs
remain distinct from external synthetic references. The schema stores block metadata
once; scoring streams vectors and reads rich metadata only for selected hits.

The default target is 320 tokens, with a hard final limit of 480 including special
tokens and up to 64 tokens of source page/ancestor context. Up to 32 overlapping
tokens may connect fragments of the same block; overlap yields to forward progress.
Fragments retain their source spans. Metadata and context reside only in the
external cache. The v2 pipeline identity prevents reuse of older byte-sliced vectors;
an explicit build recreates incompatible derived work tables while preserving the
previous published snapshot until the new generation passes validation.

## Local embedding endpoint

The external backend is disabled by default. When enabled, its model, revision,
dimensions, and cache root must be explicit. The endpoint defaults to loopback and
can be configured independently. The model revision should identify the exact
local artifact so a model change makes an old snapshot
incompatible. Requests use the configured loopback `/v1/embeddings` endpoint or
an explicitly configured filesystem Unix socket. The client does not inherit
chat credentials, proxy settings, or a cloud endpoint. The same local server must
provide a compatible `/tokenize` route accepting `content`, `add_special`,
`parse_special`, and `with_pieces` and returning a `tokens` array of integer IDs.
Its special-token policy must match the embedding route. Final inputs are counted
by that tokenizer, including the exact context and separators. Tokenizer failure
has no byte-based fallback. Requests also have
an independent UTF-8 byte safety bound. Queries over
`MATRYCA_EXTERNAL_SEMANTIC_MAX_INPUT_TOKENS` are rejected, never silently truncated.

See `.env.example` for the complete `MATRYCA_EXTERNAL_SEMANTIC_*` settings. The
legacy `MATRYCA_DUAL_EMBEDDING_ENABLED` switch remains independent; enabling the
external backend does not enable daemon indexing or legacy applicability-vector
requests.

## Maintenance and query

Export the external semantic variables in the command environment; the direct
module CLI does not load `.env`. For example, replace these placeholders with an
external cache path and the exact model alias, artifact fingerprint, and output
dimension of the locally configured endpoint:

```sh
export MATRYCA_EXTERNAL_SEMANTIC_ENABLED=true
export MATRYCA_EXTERNAL_SEMANTIC_CACHE_PATH=/path/to/external/cache
export MATRYCA_EXTERNAL_SEMANTIC_MODEL=local-model-alias
export MATRYCA_EXTERNAL_SEMANTIC_MODEL_REVISION=artifact-fingerprint
export MATRYCA_EXTERNAL_SEMANTIC_DIMENSIONS=1024
```

Run these commands from the project environment with the exact read-only graph
path:

```sh
python -m src.semantic.external_cli status --graph-root /path/to/Logseq/graph
python -m src.semantic.external_cli build --graph-root /path/to/Logseq/graph
python -m src.semantic.external_cli status --graph-root /path/to/Logseq/graph
python -m src.semantic.external_cli search --graph-root /path/to/Logseq/graph --query "synthetic query"
```

`build` is the only command that creates or replaces index files, and it writes
only beneath the external cache root. A complete compatible snapshot is required
for MCP search. Incomplete builds remain resumable and are reported as incomplete.
This repository support does not assert that the host endpoint, model artifact, or
snapshot has been deployed; enable MCP search only after status reports a complete
compatible snapshot for the intended graph.

When enabled in the Plumber worker, `search_graph` selects this backend before
constructing the legacy embedding client. When disabled, the existing legacy
semantic-search path is preserved.
