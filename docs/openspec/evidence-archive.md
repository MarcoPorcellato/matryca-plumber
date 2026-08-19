---
type: Document
---
# Governed evidence archive

## Scope

The P0 evidence archive records immutable, privacy-safe provenance for a
proposed memory candidate. It is not a memory store, retrieval index, proposal
queue, or canonical Logseq write path. It does not capture events automatically.

## Authority and placement

- Logseq Markdown remains the semantic authority.
- The archive is external to the graph and external to Shadow DB at
  `<MATRYCA_CACHE_PATH>/graphs/<private-graph-id>/evidence/events.jsonl`.
- It shares the external-cache policy with Shadow, but never opens, initializes,
  reads, or writes Shadow SQLite.
- `MATRYCA_READ_ONLY=true` permits this external archive only after the cache
  root is proven absolute and outside the graph.

## Record contract

Each `EvidenceEvent` has one proposed `MemoryCandidate` and one or more
`EvidenceRef` values. Public fields are restricted to validated identifiers,
SHA-256 digests, UTC timestamps, and bounded classifications. Raw vault text,
prompts, credentials, absolute paths, and reconstructed candidate prose are
not accepted by this P0 contract.

Its event identity may be referenced by the pure `P0EvidencePacket` coordination
contract in [biological-memory.md](biological-memory.md). That reference never
opens, replays, or writes this archive, and it does not turn a candidate into an
accepted canonical memory.

Events serialize as canonical JSON and derive an event ID from their canonical
bytes. A replay of the same event is a no-op. A complete malformed record fails
closed. A final unterminated JSON fragment is recoverable only when it has the
bounded shape of an interrupted event write; the archive fsyncs its truncation
before recording another event.

## Durability, concurrency, and limits

- Writes use a per-archive cross-process lock and `O_NOFOLLOW` final-path
  protection on POSIX hosts.
- Records append through a complete-write loop followed by `fsync`.
- Archive replay is capped at 16 MiB. Larger archives fail closed and require a
  deliberate future retention/migration contract rather than unbounded memory
  use.
- Direct construction with a hand-assembled location is rejected unless it
  reproduces the validated graph/cache identity.

## Operations

The archive is operator-local evidence, not a backup or a portable source of
truth. Preserve it when investigating a governed memory decision. Delete it
only with the whole external cache for the graph, understanding that future P0
traceability is then unavailable. Deleting it never changes Logseq Markdown or
Shadow DB, and it never authorizes a canonical write.

## Non-goals

- automatic capture or model calls;
- retrieval, clustering, curation, promotion, decay, or proactivity;
- a Shadow schema, migration, synchronization hook, or daemon bootstrap path;
- any bypass of Safe-Sync or graph write policy.
