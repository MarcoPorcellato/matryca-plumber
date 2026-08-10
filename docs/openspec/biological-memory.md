# Biological memory layer — OpenSpec (projection contract, planned v2.1+)

**Status:** planned for v2.1+ — no memory read/write path is shipped in `main`; schema and scaffolds remain proposal-stage

**Historical architecture context:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

**Active delivery tracker:** [#178 — Coordinate v2.1 memory, Safe-Sync, and import programme](https://github.com/MarcoPorcellato/matryca-plumber/issues/178)

**Roadmap source:** [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md)

**Leadership dossier:** [`AGENTIC_MEMORY_LEADERSHIP_PROGRAMME_2026-08-10.md`](../quality/AGENTIC_MEMORY_LEADERSHIP_PROGRAMME_2026-08-10.md)
**Preparation index:** [`ROADMAP_V2_PREPARATION.md`](../roadmaps/ROADMAP_V2_PREPARATION.md)

Nacre-inspired memory behavior is treated as a design reference only.
This OpenSpec is a projection contract that keeps external expectations aligned with the roadmap sequence.

---

## Canonical contract

### Source authority and projections

- **Logseq Markdown is canonical for semantic memory and approved decisions.**
- **`Shadow DB` is derived and disposable/rebuildable**: indexes, embeddings, hashes, generations, activation/utility projections, bounded caches, and aggregates are allowed there, but it is never the sole semantic authority.
- Writes to Markdown remain through approved mutation planes (OCC + official interfaces).
- No public rollout claim is accepted without a matching roadmap issue sequence and evidence row.

### Phase sequence

#### P0: evidence and provenance gate

- Governed evidence requirements apply first.
- Canonical recall envelope and idempotence rules are the acceptance basis.
- Reproducible benchmark baseline must be attached before downstream feature claims.

#### P1: hybrid retrieval, cache, and clustering

- Retrieval composition is activated only after P0 acceptance.
- Cache/fallback rules are deterministic.

#### P2: proposal queue and curation

- Governance for proposal intake, triage, curation, and traceability.
- Evidence-only acceptance and state transitions.

#### P3: procedural memory, typed activation decay, opt-in proactivity

- Typed activation decay belongs exclusively to P3.
- Typed activation decay is constrained to utility/procedural projections and does not modify or delete source truth.

## Feature-gate posture

| Variable | Contract status | Role |
| --- | --- | --- |
| `MATRYCA_MEMORY_GRAPH_ENABLED` | Not yet public contract | Future gate for derived projection operations only; it never authorizes canonical writes |

When publicly exposed, document in `.env.example` under **Advanced / high impact** with rollout and fallback policy.

## Issue mapping by phase

- **P0:** [#186](https://github.com/MarcoPorcellato/matryca-plumber/issues/186), [#447](https://github.com/MarcoPorcellato/matryca-plumber/issues/447), [#448](https://github.com/MarcoPorcellato/matryca-plumber/issues/448), [#449](https://github.com/MarcoPorcellato/matryca-plumber/issues/449)
- **P1:** [#450](https://github.com/MarcoPorcellato/matryca-plumber/issues/450), [#451](https://github.com/MarcoPorcellato/matryca-plumber/issues/451)
- **P2:** [#452](https://github.com/MarcoPorcellato/matryca-plumber/issues/452)
- **P3:** [#99](https://github.com/MarcoPorcellato/matryca-plumber/issues/99), [#453](https://github.com/MarcoPorcellato/matryca-plumber/issues/453), [#454](https://github.com/MarcoPorcellato/matryca-plumber/issues/454)

## Projection surfaces

| Existing surface | Planned extension |
| --- | --- |
| `search_graph(...)` | Add recall-focused method and scoring envelope after P0 acceptance |
| `store_fact` | Extend to support proposal and procedural pathways after P2/P3 acceptance |

## Evidence and benchmark policy

- Design references and benchmark evidence are separated.
- This spec accepts LongMemEval, LongMemEval-V2, LoCoMo, BEAM, MemoryAgentBench, and STATE-Bench as benchmark suites for evidence-gated decisions.
- Letta Evals, Mem0 memory-benchmarks, and Graphiti are treated as design/reference harness material.
- No best/SOTA/world-leading claim is made before reproducible evidence with provenance.
- Every claim must include task set, corpus/version, seed/config, and decision label.

## Safe-Sync and mutation constraints

- Memory work remains inside existing Safe-Sync boundaries.
- `MATRYCA_MEMORY_GRAPH_ENABLED` gates derived projection operations and never authorizes canonical semantic writes.
- No behavior bypasses daemon-owned paths or established safety gates.

## Future phase gates

- P0 must publish governed evidence packet and benchmark baseline before any P1/P2/P3 runtime claims.
- P1 release requires deterministic retrieval/cache/clustering gates with repeatable manifests.
- P2 release requires proposal queue and curation evidence under accepted governance.
- P3 execution requires Safe-Sync-compatible procedural/decay constraints and opt-in proactivity controls.
