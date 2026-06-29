# v2.0 — Biological Memory Layer (Nacre-inspired)

**Parent epic:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Status:** planned — schema in [`src/shadow/schema.py`](../../src/shadow/schema.py); decay in [`src/memory/decay.py`](../../src/memory/decay.py)  
**Preparation index:** [`ROADMAP_V2_PREPARATION.md`](ROADMAP_V2_PREPARATION.md) · OpenSpec: [`biological-memory.md`](../openspec/biological-memory.md)  
**Prerequisite:** [`ROADMAP_V2_SHADOW_DB.md`](ROADMAP_V2_SHADOW_DB.md) ([#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24), [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17))  
**Inspiration:** [Nacre](https://github.com/marcusschimizzi/nacre) by Marcus Sullivan (Apache-2.0) — port nativo Python, non sidecar Node  
**RFC:** [Discussion #19](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

---

## Cosa sono i due progetti

| | **Nacre** | **Matryca Plumber** |
|---|---|---|
| **Scopo** | Memory layer per agenti long-lived (mesi) | Daemon local-first per vault Logseq OG + agenti MCP/CLI |
| **Stack** | TypeScript monorepo (`@nacre/core`, parser, viz, CLI) | Python 3.12 + React Sovereign UI |
| **Storage** | `SqliteStore` (WAL, schema v5, embeddings) | JSON sidecars → **Shadow DB** `shadow.sqlite` |
| **Unità di memoria** | Nodi tipizzati + archi tipizzati | Blocchi/pagine Logseq + wikilink + indice semantico block-level |
| **Licenza** | Apache-2.0 — Copyright 2026 Marcus Sullivan | Apache-2.0 — Copyright 2026 Marco Porcellato & Matryca.ai |

**Principio:** portare il motore di memoria biologica di Nacre *dentro* l'infrastruttura Logseq esistente — non sostituire il parser o il modello a blocchi.

---

## Gap analysis — cosa fa Nacre che Matryca non ha ancora

### 1. Decay / reinforcement (P0)

```
weight(t) = baseWeight × e^(-λt / stability)
stability = 1 + β × ln(reinforcementCount + 1)
```

Sorgente Nacre: [`packages/core/src/decay.ts`](https://github.com/marcusschimizzi/nacre/blob/main/packages/core/src/decay.ts)  
Matryca oggi: nessun decay sulle connessioni.

### 2. Hybrid recall a 4 segnali (P0)

Semantic + graph walk + recency + importance — [`recall.ts`](https://github.com/marcusschimizzi/nacre/blob/main/packages/core/src/recall.ts).  
Matryca: BM25 + dual embedding + link hops, senza fusione unificata.

### 3. Memoria episodica + procedurale (P1–P2)

Episodi sessione + procedure (lesson/preference/skill/…).  
Matryca: solo `store_fact` → `matryca-config.md` e Journey Log operativo.

### 4. Intelligence layer zero-LLM (P1)

Connection suggestions, emerging/fading topics — [`intelligence.ts`](https://github.com/marcusschimizzi/nacre/blob/main/packages/core/src/intelligence.ts).  
Matryca: overlap parziale (`unlinked_mentions`, `entity_consolidation`, `insights_engine`, `semantic_clustering`).

### 5. Consolidation sleep/wake (P0)

Batch idle post-sync Shadow DB → Phase 3 daemon.

### 6. MCP memory-native

| Nacre | Matryca oggi |
|---|---|
| `nacre_recall` | `search_graph` — parziale |
| `nacre_brief` | dashboard + Graph Insights — parziale |
| `nacre_remember` | `store_fact` — limitato |
| `nacre_forget` / `nacre_feedback` / `nacre_lesson` | assenti |

---

## Cosa Matryca ha già (non duplicare)

- Paradigma Logseq outliner, OCC, Safe-Sync ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25))
- Cognitive lint LLM (MARPA, healer, property hygiene, auto-split, backlink backprop)
- L1/L2 Karpathy model ([`l1_memory.py`](../../src/agent/l1_memory.py))
- Ingest atomico + Trust & Safety tiers + dual embedding applicability

---

## Roadmap di implementazione

### Fase A — Fondamenta in Shadow DB

DDL in [`src/shadow/schema.py`](../../src/shadow/schema.py). Package [`src/memory/`](../../src/memory/):

| Modulo | Sorgente Nacre |
|--------|----------------|
| `decay.py` | `decay.ts` |
| `recall.py` | `recall.ts` |
| `intelligence.py` | `intelligence.ts` |
| `resolve.py` | `resolve.ts` (+ `alias_index.py`) |
| `consolidate.py` | pipeline sleep/wake |

Estrazione entità **Logseq-native** (non `@nacre/parser`):

- **Structural:** wikilink, block-ref, tags, page properties via `logseq-matryca-parser`
- **Co-occurrence:** stesso sotto-albero di blocchi (outliner-aware)
- **Custom:** entity-map YAML in `.matryca/`

Env: `MATRYCA_MEMORY_GRAPH_ENABLED=false` (opt-in alpha).

### Fase B — Hybrid recall

`search_graph(method="recall")` in [`graph_dispatch.py`](../../src/agent/graph_dispatch.py):

```
final = w_sem×semantic + w_graph×graphWalk + w_recency×recency + w_importance×importance
```

### Fase C — Episodi + procedure

SQLite + mirror umano su `pages/Matryca Procedures.md`. Estendere `store_fact` per `kind=lesson|preference|…`.

### Fase D — Intelligence & alerts

`memory_intelligence.py` → pagina `Matryca Memory Alerts` + pannello Sovereign UI.

### Fase E — Temporal & viz (post-MVP)

`memory_snapshots`, `as_of` recall, grafo 2D in UI.

### Fase F — Hive multi-vault (opzionale)

Solo se emerge demand reale.

---

## Priorità

| Priorità | Feature |
|---|---|
| P0 | Decay + consolidation sleep |
| P0 | Hybrid recall unificato |
| P1 | Intelligence alerts |
| P1 | Procedure memory |
| P2 | Episodic memory |
| P2 | Temporal snapshots |
| P3 | 2D graph viz |
| P3 | Hive federation |

---

## Conformità Apache-2.0

Entrambi i progetti sono Apache-2.0. Per ogni merge di codice portato da Nacre:

1. Mantieni [`LICENSE`](../../LICENSE) invariato
2. Aggiorna [`NOTICE`](../../NOTICE) con attribuzione Marcus Sullivan / Nacre
3. Header SPDX nei file `src/memory/*.py` portati
4. [`docs/THIRD_PARTY.md`](../THIRD_PARTY.md) al primo merge (file-per-file map)
5. Test pytest con parità numerica decay (half-life table Nacre)
6. Non usare “Nacre” come brand Matryca — solo attribuzione in NOTICE/README

Checklist dettagliata: sezione “Conformità Apache-2.0” nel piano originale (mantainer reference).

---

## Rischi

| Rischio | Mitigazione |
|---|---|
| Duplicazione semantic JSON | Shadow DB source of truth v2; deprecazione graduale JSON |
| `maintenance_daemon.py` ~3200 righe | Phase 3 in modulo dedicato ([#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57)) |
| Parser Nacre ≠ Logseq | Solo `logseq-matryca-parser` |
| Embedding dimension mismatch | Meta in `shadow_meta`; stesso fix documentato in Nacre ROADMAP |
| Scope creep | Flag opt-in; ship decay+recall prima di viz/hive |

---

## Prossimi passi

1. ~~Salvare roadmap in repo~~ (this file)
2. Issue **Biological Memory Layer** linkata a #20/#24
3. RFC Discussion #19: mapping block UUID → memory node
4. `src/memory/decay.py` + test parità Nacre
5. Prototipo consolidation su 100 pagine con `MATRYCA_MEMORY_GRAPH_ENABLED=true`
6. `NOTICE` + `docs/THIRD_PARTY.md` al primo merge codice Nacre
