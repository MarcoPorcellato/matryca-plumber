---
type: Contract
title: Pocket V1 contract bundle
description: Public, content-free contract for deterministic Pocket V1 conformance bundles.
status: active
classification: active
audience: [maintainer, contributor]
owner: core-runtime
supersedes: []
related: []
---

# Pocket V1 contract bundle

This repository is the sole authority for the closed Pocket V1 models, JSON
Schemas, canonical vectors, synthetic fixtures, and deterministic contract
bundle builder. This document describes the contract bundle; it is not a pack
producer or consumer integration.

## Models and scalar limits

The public record models are `PackManifestV1`, `DocumentV1`, and `EvidenceV1`.
`SourceRevisionV1` and `PackFileV1` are closed nested definitions;
`SourceRevisionV1` is also a Python domain record. Bundle validation uses the
closed `BundleFileV1` and `ContractBundleManifestV1` records and returns a
`BundleReceipt`. All records are frozen and closed: unknown fields are
rejected.

| Value | Limit or form |
| --- | --- |
| Stable identifiers, generator ID, and key ID | lowercase ASCII identifier, at most 64 characters |
| Repository slug | `owner/repository`, at most 200 characters |
| Commit and SHA-256 digest | exactly 40 and 64 lowercase hexadecimal characters, respectively |
| Paths | NFC UTF-8, safe relative `/` paths, at most 4,096 bytes; bundle paths also reject Cc and Cs Unicode categories |
| Media type | lowercase media type, at most 127 characters |
| Document title / cited text | NFC, 1–1,024 / 1–16,384 characters |
| Sources / declared payload files | 1–128 / 0–4,096 entries |
| Document or evidence records | at most 1,000,000 per record family |
| Locator positions and record counts | non-negative or positive, as applicable, and at most 1,000,000 |
| Declared payload size | 0 through 2^31 bytes |
| Canonical JSON integer | 0 through 2^63−1 |

The bundle builder and verifier additionally limit every bundle file, including
`bundle-manifest.json`, to 32 MiB, all non-manifest bundle files to 256 MiB
total, and each scanned directory to 32,768 entries. The manifest byte cap is
applied before stdlib JSON parsing; the manifest file-count check runs after
`json.loads` and before Pydantic materialization. This is not a streaming-parser
claim.

## Content roots and receipts

For a validated, path-sorted `PackManifestV1.files` array `FILES`, the pack
content root is:

```text
SHA-256(PocketCanonicalJsonV1({"files": FILES}))
```

For the bundle's lexically path-sorted list of every file except
`bundle-manifest.json`, the bundle content root uses the same formula. The
bundle digest is `SHA-256` of the canonical `bundle-manifest.json` bytes. The
manifest excludes itself, so neither calculation is self-referential. Build and
verify emit only a JSON receipt with `bundle_digest`, `content_root`, and
`file_count`.

## Canonical JSON and failures

Pocket Canonical JSON V1 admits NFC strings, ASCII snake_case object keys,
booleans, non-negative signed 64-bit integers, lists, and objects. It rejects
`null` and floating-point values. Output is UTF-8 without a BOM, insignificant
whitespace, or a trailing newline; object keys are lexically sorted and arrays
preserve their validated order. Exact language-neutral vectors are committed at
`contracts/pocket/v1/vectors/canonical-json.json`.

Stable content-free error codes include:

| Area | Codes |
| --- | --- |
| Canonical values | `invalid_object_key`, `integer_out_of_range`, `non_nfc_string`, `unsupported_json_type` |
| Model scalars | `invalid_source_id`, `invalid_repository_slug`, `invalid_source_commit`, `invalid_generator_id`, `invalid_generator_commit`, `invalid_key_id`, `invalid_pack_id`, `invalid_created_at`, `invalid_media_type`, `invalid_sha256`, `invalid_content_root`, `invalid_document_id`, `invalid_evidence_id`, `invalid_locator_range`, `unsafe_bundle_path` |
| Model and record-set invariants | `unexpected_fields`, `noncanonical_order`, `duplicate_source_id`, `duplicate_source_revision`, `duplicate_file_path`, `duplicate_document_id`, `duplicate_evidence_id`, `missing_source_reference`, `missing_document_reference`, `too_many_records`, `content_root_mismatch` |
| Bundle assembly and verification | `unsafe_source_root`, `unsafe_output_parent`, `unsafe_output_root`, `output_not_empty`, `source_bundle_manifest`, `nonregular_source_file`, `nonregular_bundle_file`, `too_many_bundle_entries`, `too_many_bundle_files`, `bundle_file_too_large`, `bundle_too_large`, `invalid_bundle_manifest`, `missing_bundle_manifest`, `missing_bundle_file`, `unexpected_bundle_file`, `duplicate_bundle_file`, `bundle_digest_mismatch`, `source_changed`, `bundle_write_failed`, `bundle_publish_failed`, `bundle_publish_rollback_failed`, `staging_cleanup_failed`, `bundle_changed`, `unsafe_bundle_root`, `safe_open_unsupported` |

The repository script prints only the stable error code to standard error and
returns exit status 2 for a `PocketContractError`; it writes no receipt on that
failure path.

## Fixtures and commands

The authoritative contract root is `contracts/pocket/v1`. Every fixture case
in `fixtures/valid` or `fixtures/invalid` contains exactly `manifest.json`,
`documents.jsonl`, `evidence.jsonl`, and `expectation.json`. The expectation is
harness-only metadata; all fixtures, names, commits, paths, titles, and cited
text are synthetic. They do not qualify a real pack.

The following examples target the repository's documented POSIX shell workflow
and use an explicit local temporary directory:

```bash
POCKET_BUNDLE_DIR="${TMPDIR:-/tmp}/pocket-contract-v1"
rtk uv run python scripts/build_pocket_contract_bundle.py build --source-dir contracts/pocket/v1 --output-dir "$POCKET_BUNDLE_DIR"
rtk uv run python scripts/build_pocket_contract_bundle.py verify --bundle-dir "$POCKET_BUNDLE_DIR"
```

Consumers pin the exact Plumber commit and bundle digest, copy only files named
by `bundle-manifest.json`, and never fetch a moving branch.

`signature_algorithm="ed25519"` and `key_id` are structural metadata only.
Alpha 1A performs no cryptographic signing, key handling, or signature
verification.

## Non-goals

This contract does not create real packs or real content; integrate Knowledge
or Pocket; use a network, persistence, model, runtime route, MCP surface, or
consumer repository; or qualify signing, a native platform, a release, or any
Alpha 1B or Alpha 1C work.
