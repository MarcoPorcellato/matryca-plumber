# Historical Logseq DB Capability Baseline — 2026-09-05

> **Historical/non-authorizing.** This baseline is retained as evidence of the
> prior consumer-policy design and is superseded for execution by the accepted
> [Plumber Logseq gateway authority](../decisions/2026-09-05-plumber-logseq-gateway-authority.md).
> It does not authorize a Trama host adapter or `trama.logseq.read/v1` authority.
> `GraphReadPort remains filesystem/Shadow-only`; no runtime or DB capability is
> introduced by this historical evidence.

## Status

This is Plumber's historical consumer evidence-policy baseline. Trama's
synthetic OG qualification is recorded as evidence at
`main@9905e8a36acb83a17a33b702a5fa620d6bfed185`; it does not establish current
DTO authority or a read-only operation shape.

No Logseq DB execution was performed. DB-host semantics, page/subtree parity,
graph binding, lifecycle, transport, credential storage, event ordering,
cursor semantics, and conflict semantics are **unverified**.

The three Task 3 fixtures demonstrate policy handling: one unverified baseline
and two rejected cases (an explicitly incomplete subtree observation and direct
internal-database access). The rejected fixtures are synthetic policy inputs,
not captured host output. Their overall fixture digest and each of their three
operation-result digests are separately reproducible from named synthetic
bases. Each operation-level `result_sha256` aliases only that operation's Trama
provenance `evidence_digest`; there is no aggregate result-truth field.

No fixture has `qualification_state: "supported"`. This baseline proves
consumer-policy rejection, not Logseq DB support.

## Admission boundary

The versioned profile consumes Trama's request/result envelopes and exact
provenance fields without copying their wire schema. Plumber evidence keeps
`qualification_state` separate from Trama runtime outcomes.

Future `supported` evidence requires exactly one successful outer evidence
record for each required operation: `graph.identify`, `page.read`, and
`block.subtree.read.complete`. Each record binds result producer identity to
provenance producer, result and exercised capability coverage, `db_native` /
`logseq_db_native` provenance, a privacy-safe opaque provenance source
reference, graph binding, and its own result digest. Complete ordered parentage
is required specifically on the subtree record.

The profile's Trama commit pin is historical static contract-authority metadata
only. Future host evidence must independently record exact 40-hex
`trama_commit` and `probe_commit` values. They may legitimately coincide with
each other or with the historical authority pin when the exact evidence calls
for that relationship. An operation provenance `source_reference` is an opaque
graph/profile-scoped binding, not a Git commit; it may equal graph binding when
the host contract makes that appropriate. Future evidence also requires
selected-host identity, a separately bound artifact/build digest, fixture
digest, a stable non-foreign session, bounded sanitized fields, and zero forbidden state
change. Transport identity is conditional: CLI evidence needs its CLI artifact,
SDK evidence its SDK version, and MCP stdio evidence its server identity.

The historical source pin is Trama commit `9905e8a36acb83a17a33b702a5fa620d6bfed185`.
The exact historical source paths are `packages/contracts/src/trama_contracts/models.py`
(Git blob SHA-1 `cd665decd41ccb2061b5355bc2ec20273fcc005e`),
`docs/contracts/LOGSEQ_READ_CONTRACT_V1.md` (Git blob SHA-1
`b59f92270338705b365346a2998a8174a559f0cd`), and
`docs/spikes/evidence/python-read-contract-v1/862c5c89157f28c1985cde6145fc2c8af04a70b4.md`
(Git blob SHA-1 `20730f3e922b524c43a4c46e7d38374c68e2229d`).

This is a test-only quality boundary, not a runtime capability or DB support
claim.
