---
type: Document
---
# Dual embedding strategy (Master RFC — Phase 3)

**Implementation:** `src/semantic/`  
**Related:** [`ingest.md`](ingest.md), [`llm-performance.md`](llm-performance.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md)

Matryca Plumber can index each Logseq block with **two** dense vectors:

| Vector | Source text |
|--------|-------------|
| `vec_content` | Raw block markdown (`content` + `clean_text`) |
| `vec_applicability` | One-sentence LLM “when is this useful?” profile |

Retrieval embeds the user query once and scores blocks with:

`final_score = w_content * cos(query, vec_content) + w_app * cos(query, vec_applicability)`

BM25 (`search_graph` / `method=bm25`) and TF-IDF page clustering (`semantic_clustering.py`) are unchanged.

---

## Feature flag and rollout

| Variable | Default | Role |
|----------|---------|------|
| `MATRYCA_DUAL_EMBEDDING_ENABLED` | `false` | Daemon dual-indexes after semantic writes when `true` |
| `MATRYCA_WEIGHT_CONTENT` | `0.5` | Hybrid weight for content cosine |
| `MATRYCA_WEIGHT_APPLICABILITY` | `0.5` | Hybrid weight for applicability cosine |
| `MATRYCA_EMBEDDING_MODEL` | `text-embedding-3-small` | `/v1/embeddings` model id |
| `MATRYCA_EMBEDDING_BASE_URL` | _(empty)_ | Falls back to `MATRYCA_LM_BASE_URL` / `LLM_BASE_URL` |

**Not** run inside `ingest_document` (would timeout). Ingest writes markdown; the daemon indexes on a later semantic cycle when the flag is on.

---

## Storage

`{graph}/.matryca_semantic_cache/block_vectors.json` — versioned JSON map `block_uuid → {vec_content, vec_applicability, applicability_text, page_title, …}`.

---

## MCP search

`search_graph` with `method=semantic` — requires flag + populated `block_vectors.json`.

---

## Modules

| Module | Role |
|--------|------|
| `applicability.py` | `synthesize_applicability`, `InstructorApplicabilityLLM` |
| `embedding.py` | `EmbeddingClient`, `OpenAICompatibleEmbeddingClient` |
| `store.py` | `BlockVectorStore` persistence |
| `indexer.py` | `index_page_blocks` (blocks with `id::` only) |
| `search.py` | `hybrid_block_search`, `format_semantic_search_markdown` |

**Tests:** `tests/test_dual_embedding.py`
