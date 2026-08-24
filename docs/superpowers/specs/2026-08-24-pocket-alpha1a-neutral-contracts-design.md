# Pocket Alpha 1A Neutral Contracts Design

Date: 2026-08-24

Status: design approved; implementation requires a separate execution `GO`

## 1. Purpose

Alpha 1A defines the smallest language-neutral contract surface needed for the
first useful Matryca Pocket vertical slice. A later Knowledge producer will
build a deterministic Mobile Knowledge Pack, and a later Pocket consumer will
import that pack, search it offline, and show a result with its source, exact
commit, and citation.

This tranche changes Plumber only. It creates no pack, Android behavior,
personal store, network path, model runtime, or production signing material.

### 1.1 Design provenance

This design was reviewed against:

- freshly fetched Plumber `origin/main` at
  `48eae93b1152c9fe7d1f19d63de3f781b686932e`;
- Pocket Alpha 0 `main` at
  `574a5ba6d734187eb58f3c3d36a45fcaa146b94b`;
- the live Plumber closed-model and deterministic-contract patterns.

The Matryca Knowledge MCP freshness check was attempted but failed because its
runtime could not locate `sources.toml`. No claim in this design relies on that
derived projection as current evidence.

## 2. Delivery sequence and ownership

The approved Alpha 1 sequence has three independently gated tranches:

1. **Alpha 1A — neutral contracts in Plumber.** Plumber owns schemas,
   content-free conformance fixtures, canonicalization vectors, and the
   deterministic contract-bundle builder.
2. **Alpha 1B — pack production in Matryca Knowledge.** Knowledge pins one
   exact Alpha 1A bundle digest and produces synthetic packs plus one bounded
   real acceptance pack.
3. **Alpha 1C — verification and Library UI in Pocket.** Pocket pins the same
   bundle digest, imports a selected `.mkp`, verifies it, searches it through
   FTS, and displays source provenance.

Consumers copy only manifest-listed contract artifacts and record the Plumber
commit plus bundle digest. They never import Plumber Python code, fetch a
moving branch, or treat the derived Matryca Knowledge projection as source
authority.

## 3. Alpha 1A scope

Alpha 1A produces four closed top-level V1 record families:

- `SourceRevisionV1`: one stable source identifier, repository slug, and exact
  40-character lowercase Git commit;
- `PackManifestV1`: pack identity, explicit build time, generator identity,
  contract version, signature metadata, ordered source revisions, ordered
  payload inventory, and payload content root;
- `DocumentV1`: one stable document identifier, source identifier, title,
  source-relative path, and media type;
- `EvidenceV1`: one stable evidence identifier, document identifier, bounded
  locator, and bounded cited text.

`PackFileV1` and `SourceRevisionV1` are definitions embedded in the public
pack-manifest schema; `SourceRevisionV1` is also treated as a top-level domain
record by the Python model. The three public schema files remain the pack
manifest, document, and evidence schemas.

The implementation also produces JSON Schemas, valid and invalid synthetic
fixtures, canonical byte vectors, a deterministic bundle manifest, a verifier,
and concise contract documentation.

### 3.1 Explicit non-goals

Alpha 1A does not add:

- answer envelopes, claims, chat, Notebook, sync, model, or inference schemas;
- pack payloads, SQLite schemas, FTS, Atlas data, graph contracts, or Android
  code;
- real repository content, real citations, credentials, secrets, private
  keys, production public keys, or usable signatures;
- network access, downloads, runtime services, database writes, or source
  refreshes;
- a new dependency solely for canonical JSON.

Signature metadata is structural only: V1 identifies `ed25519` and a bounded
`key_id`, while cryptographic generation, trust roots, delegation, revocation,
and signature verification belong to separately reviewed Alpha 1B and 1C
designs.

## 4. Contract model

All models are immutable and closed. Unknown fields fail validation. JSON
Schemas set `additionalProperties` to `false` recursively. Optional properties
are omitted rather than serialized as `null`; JSON `null` and floating-point
numbers are outside the V1 canonical domain.

### 4.1 Common scalar rules

- schema identifiers and stable IDs use bounded lowercase ASCII identifiers;
- repository slugs use a bounded `owner/repository` form;
- Git commits are exactly 40 lowercase hexadecimal characters;
- SHA-256 values are exactly 64 lowercase hexadecimal characters;
- relative paths are NFC UTF-8, use `/`, and reject empty segments, `.`, `..`,
  absolute paths, backslashes, NUL, control characters, and duplicate logical
  names;
- integers are non-negative signed 64-bit values unless a tighter field bound
  applies;
- human-readable strings must already be valid NFC Unicode and obey explicit
  byte and character limits; validators reject instead of silently normalizing;
- arrays that represent sets have contract-defined sort keys and reject
  duplicates or noncanonical order.

### 4.2 `SourceRevisionV1`

Fields:

- `source_id`: stable lowercase identifier;
- `repository_slug`: bounded owner/repository identity;
- `source_commit`: exact Git commit.

The `PackManifestV1.sources` array is sorted by `source_id`. Duplicate source
identifiers or repository/commit pairs fail closed.

### 4.3 `PackFileV1`

Fields:

- `path`: safe payload-relative path;
- `media_type`: bounded lowercase media type;
- `size_bytes`: exact uncompressed byte count;
- `sha256`: payload digest;
- `record_count`: non-negative logical record count.

The files array is sorted by `path`. Manifest and signature paths are not
payload entries, preventing self-reference.

### 4.4 `PackManifestV1`

Fields:

- `format_version`: fixed `matryca-pocket-pack.v1`;
- `contract_version`: fixed `matryca-pocket-contract.v1`;
- `pack_id`: exact lowercase canonical UUIDv7 string supplied by the caller;
- `created_at`: explicit UTC timestamp supplied by the caller, never read from
  the build clock;
- `generator_id` and `generator_commit`: reproducible producer identity;
- `signature_algorithm`: fixed `ed25519`;
- `key_id`: bounded public key identifier, not key material;
- `sources`: canonical `SourceRevisionV1` array;
- `files`: canonical `PackFileV1` array;
- `content_root`: SHA-256 over the Pocket Canonical JSON V1 bytes of
  `{"files": FILES}`, where `FILES` is the validated path-sorted array and the
  object contains no other field.

The contract does not claim that a declared validation ran. Executed checks
belong in later build and admission receipts.

### 4.5 `DocumentV1`

Fields:

- `document_id`: stable identifier unique within the pack;
- `source_id`: reference to a manifest source;
- `title`: bounded NFC display title;
- `source_path`: safe source-relative path;
- `media_type`: bounded media type.

### 4.6 `EvidenceV1`

Fields:

- `evidence_id`: stable identifier unique within the pack;
- `document_id`: reference to an existing document;
- `locator_kind`: one of `line_range`, `page`, or `record`;
- `locator_start` and `locator_end`: positive bounded integers with end not
  smaller than start;
- `cited_text`: bounded NFC text shown to the user.

Cross-record validation requires every document source to exist, every
evidence document to exist, and identifiers to remain unique. Source commit is
resolved through `EvidenceV1 -> DocumentV1 -> SourceRevisionV1`, avoiding a
second, potentially inconsistent commit field.

## 5. Canonical JSON profile

Pocket Canonical JSON V1 is a deliberately restricted, dependency-free subset
compatible with RFC 8785 for admitted values:

- input models have already rejected floats, `null`, non-NFC strings, invalid
  Unicode, and out-of-range integers;
- object keys are ASCII `snake_case` and serialized in lexical byte order;
- arrays preserve their already validated contract order;
- output is UTF-8 with no byte-order mark, insignificant whitespace, or
  trailing newline;
- strings use the JSON escapes required for quotation mark, reverse solidus,
  and control characters, while other Unicode is emitted as UTF-8;
- integers use the shortest base-10 representation.

The implementation claims compatibility only for this admitted subset, not a
general RFC 8785 implementation. Language-neutral golden vectors include ASCII,
Italian text, combining-character rejection, boundary integers, nested objects,
and ordered arrays. Python, future Knowledge code, and future Kotlin code must
produce the exact expected bytes and SHA-256 values.

## 6. Contract bundle

The builder accepts an explicit source directory and a new or empty output
directory. It never downloads, resolves a branch, reads a clock, or overwrites
an existing nonempty destination.

The output contains:

```text
bundle-manifest.json
schemas/pack-manifest.schema.json
schemas/document.schema.json
schemas/evidence.schema.json
fixtures/valid/...
fixtures/invalid/...
vectors/canonical-json.json
```

Each conformance case is a directory containing `manifest.json`,
`documents.jsonl`, `evidence.jsonl`, and `expectation.json`. Manifest and record
files are contract inputs. `expectation.json` is harness-only metadata naming
`valid` or one stable expected error code; it is never a Mobile Knowledge Pack
payload. JSONL records use one canonical object plus a final LF per row and are
ordered by their stable identifier. Cross-record validation runs over the
complete case, not an isolated row.

`bundle-manifest.json` lists every other file in lexical path order with exact
size and SHA-256. Its `content_root` is the SHA-256 over the canonical bytes of
`{"files": FILES}` using that ordered list; the bundle digest is the SHA-256 of
the canonical bundle-manifest bytes. The manifest excludes itself, so neither
digest is self-referential.

The verifier rejects missing, extra, duplicated, renamed, altered, unsafe, or
non-regular files and returns stable content-free error codes. It does not emit
fixture bodies, user paths, or source content in errors.

## 7. Files and dependency direction

Planned implementation files:

```text
contracts/pocket/v1/
src/contracts/__init__.py
src/contracts/pocket/__init__.py
src/contracts/pocket/models.py
src/contracts/pocket/canonical.py
src/contracts/pocket/bundle.py
tests/contracts/pocket/
scripts/build_pocket_contract_bundle.py
docs/contracts/POCKET_V1.md
```

`models.py` owns value invariants, `canonical.py` owns admitted-value
serialization, and `bundle.py` owns filesystem bundle assembly and verification.
The script is a thin adapter. Core contract modules do not import MCP, CLI,
graph, Shadow, agent, daemon, Knowledge, Pocket, or Android surfaces. No second
write path or general-purpose repository abstraction is introduced.

## 8. Errors and failure behavior

Validation errors use stable lowercase codes such as
`invalid_source_commit`, `unexpected_fields`, `noncanonical_order`,
`duplicate_document_id`, `missing_document_reference`, `unsafe_bundle_path`,
and `bundle_digest_mismatch`. Human diagnostics may add bounded field names and
counts but never fixture content, cited text, absolute paths, or credentials.

The builder fails before publishing output when validation is incomplete. It
builds in a sibling temporary directory and renames the completed directory
only after self-verification. Failure leaves the requested destination absent
and removes its temporary directory; a caller may retain a separate bounded
error receipt only when the execution envelope explicitly authorizes it.

## 9. Test strategy

Implementation follows test-driven development:

1. focused tests fail because the Pocket contract modules do not exist;
2. valid fixtures pass both structural JSON Schema validation and the complete
   Pydantic/semantic contract validation;
3. structurally invalid fixtures fail both layers, while semantically invalid
   fixtures may pass JSON Schema and must fail the complete contract validator
   with the declared stable code;
4. unknown fields, malformed digests, unsafe paths, duplicate IDs,
   noncanonical ordering, broken references, Unicode violations, and numeric
   bounds have explicit negative coverage;
5. canonical golden vectors assert exact bytes and digests;
6. two builds from identical explicit inputs in distinct empty directories
   produce byte-identical trees and the same bundle digest;
7. one-byte alteration, missing file, extra file, and manifest mutation make
   verification fail closed;
8. the focused suite, Ruff, mypy, documentation gates, and full Plumber CI pass
   on the exact implementation commit.

Synthetic fixtures contain invented repositories, commits, paths, titles, and
citations. Alpha 1A test artifacts cannot be presented as a real Mobile
Knowledge Pack qualification.

## 10. Execution and review gates

The canonical Plumber checkout observed during design was dirty and behind its
upstream. Implementation must therefore start in a new isolated worktree from
a freshly fetched, explicitly recorded `origin/main`; it must not modify,
stash, reset, clean, or reinterpret the canonical checkout's existing work.

Before implementation, the execution envelope records the exact base commit,
allowed paths, writer, dependency policy, checks, stop conditions, and Git
authorization. Run impact analysis before editing existing symbols and
`detect_changes` before a commit, as required by Plumber's repository policy.

Stop without an implementation commit if:

- the base differs from the approved execution envelope;
- a new dependency becomes necessary without separate admission;
- structural JSON Schema and Pydantic validation disagree on an invariant both
  layers are specified to enforce;
- canonical vectors differ across two runs;
- any real content, secret, key material, network access, or out-of-scope
  repository change appears;
- the full required verification cannot finish green.

The Matryca Knowledge MCP status check failed during design because its runtime
could not locate `sources.toml`. This is a freshness limitation of the derived
research plane, not permission to refresh it or a reason to override live
source repositories. Recheck the service before implementation and record an
unresolved degraded state if it remains unavailable.

## 11. Acceptance criteria

Alpha 1A is complete only when one exact Plumber commit provides:

- the four closed contract record families and three public JSON Schemas;
- content-free valid, invalid, and canonical-vector fixtures;
- deterministic build and strict verification of the contract bundle;
- an explicit `schema_status` and `contract_status` for every fixture, with
  structural parity where both layers enforce the invariant and semantic
  failures owned by the complete Pydantic/cross-record validator;
- byte-identical outputs across two clean builds;
- focused and full verification receipts bound to the exact commit;
- no real Matryca content, runtime integration, consumer edit, new dependency,
  network behavior, secret, key material, push, merge, or release beyond the
  separately authorized execution envelope.

Completion of Alpha 1A authorizes neither Alpha 1B nor Alpha 1C. Each receives
its own reviewed design, execution `GO`, isolated worktree, and evidence packet.
