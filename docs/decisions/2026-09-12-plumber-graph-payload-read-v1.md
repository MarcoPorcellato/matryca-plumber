---
type: Decision
title: Plumber graph payload read v1 semantics
description: Bounded, additive payload semantics for future session-bound page and complete-subtree reads.
resource: contracts/plumber.graph.payload.read/v1/
tags: [architecture, contracts, logseq, payload, privacy, interoperability]
status: accepted
classification: active
audience: [maintainer, contributor, operator]
owner: core-runtime
---

# Plumber graph payload read v1 semantics

## Decision scope

This decision freezes the semantics required before the static
`plumber.graph.payload.read/v1` artifact can be written. The contract is an
additive, bounded payload family for one page and one complete ordered block
subtree. It does not amend `plumber.graph.read/v1`, qualify a Logseq host,
create a runtime route, or establish Logseq DB support.

The accepted [Plumber Logseq gateway authority](2026-09-05-plumber-logseq-gateway-authority.md)
continues to own dependency direction. The active
[gateway design](../superpowers/specs/2026-09-06-logseq-db-read-only-gateway-design.md)
continues to own transport selection, evidence gates, and prohibited paths.
This decision only resolves the payload policies that those documents
deliberately deferred.

## Additive identity model

`plumber.graph.read/v1` remains the sole identity and session vocabulary. Its
static bytes and content-free result shapes remain unchanged.

The payload family declares the same three capability names:

- `graph.identify`;
- `page.read`;
- `block.subtree.read.complete`.

Its `graph.identify` operation record does not create a second graph identity.
It references one successful `plumber.graph.read/v1` identity result by
contract ID, schema version, and exact result digest, then repeats the same
graph, session, and source-revision bindings. Any disagreement is rejected.

`GraphReadPort` remains filesystem/Shadow-only. A future DB session adapter
must use the separate Plumber session boundary and must never be selected by
`get_graph_read_port`.

## Text and page representation

A passing page result contains:

- one opaque `page_id`;
- the exact host-provided page title;
- zero or more eligible typed properties.

A DB page is a container. Payload v1 therefore does not invent a concatenated
page-body string. Block content is delivered only by the complete-subtree
operation.

Titles and block text are valid UTF-8 strings. The producer preserves the host
code-point sequence and embedded newline characters exactly as exposed by the
qualified structured host surface. It performs no trimming, case folding,
Unicode normalization, Markdown conversion, or display-width truncation.
Missing text is not silently converted to an empty string; a valid empty block
title remains an explicit empty string.

This distinction follows the upstream DB semantics observed on 2026-09-12 at
official Logseq commit `be800f171172c259d4dd942346e4d247a0783738`, where
DB block text is exposed as a title and DB properties are first-class entities
rather than Markdown `key:: value` text. The upstream developer guides are
context, not transport qualification:

- [Logseq DB properties guide](https://github.com/logseq/logseq/blob/be800f171172c259d4dd942346e4d247a0783738/libs/guides/db_properties_guide.md);
- [Logseq CLI guide](https://github.com/logseq/logseq/blob/be800f171172c259d4dd942346e4d247a0783738/docs/cli/logseq-cli.md).

## Complete ordered subtree representation

A passing subtree result includes the selected root and at least one node.
Each node contains:

- an opaque block ID;
- `parent_id`;
- a zero-based sibling `ordinal`;
- the exact block text;
- zero or more eligible typed properties.

The projection root uses `parent_id: null` and `ordinal: 0`. This marks the
requested projection boundary; it does not assert that the source block lacks
a parent outside the result. Every other parent must appear earlier in the
same result.

Wire order is depth-first preorder: parent before descendants, siblings in
ascending ordinal order. Ordinals restart at zero for each parent and are
contiguous. IDs are unique. `complete: true` means every descendant of the
selected root that exists at the bound source revision is present. Payload v1
has no partial success, cursor, pagination, or truncated success.

## Typed-property projection

Properties are an explicit projection, never raw host objects. A property is
eligible only when all of these conditions hold:

1. its key, wire type, cardinality, and required/optional status are declared
   by the consumer profile;
2. the producer profile declares that exact key, wire type, and cardinality;
3. the qualified host marks it public and not hidden;
4. its value and cardinality fit this decision and the bound limits.

The v1 allowlist contains these wire types:

| Wire type | Accepted value |
| --- | --- |
| `text` | UTF-8 string, including an empty string |
| `number` | Finite IEEE-754 binary64 JSON number that survives RFC 8785 serialization with the same binary64 value; negative zero is rejected |
| `boolean` | JSON `true` or `false` |
| `date` | RFC 3339 `full-date` string, years `0001` through `9999`, with Gregorian calendar and leap-day validation |
| `url` | Validated ASCII absolute HTTP(S) URL under the rules below |
| `node-reference` | Opaque target ID and optional UTF-8 display label |

Every property declaration, not the type itself, carries cardinality `one` or
`many`. A many-valued property is a homogeneous array with no duplicate
canonical values. Because host collection order is not treated as semantic,
its wire values are ordered by the UTF-8 bytes of each RFC 8785 canonical JSON
value. Properties are ordered by ascending UTF-8 key bytes.

The URL wire value is an ASCII URI valid under RFC 3986 with lowercase `http`
or `https` scheme and no user-information component. Its non-empty host is
exactly one of: lowercase ASCII LDH DNS labels, canonical dotted-decimal IPv4,
or a bracketed RFC 3986 IPv6 literal without a zone identifier. An optional
decimal port is from 1 through 65535. Path, query, and fragment use only the
ASCII characters permitted for those RFC 3986 components, with well-formed
percent escapes using uppercase hexadecimal. Whitespace, control characters,
backslashes, Unicode host names, empty DNS labels, and malformed escapes are
rejected. Default ports and empty paths are not rewritten by the payload
producer; a host value that is not already in this accepted form is
unsupported.

A consumer profile marks every declared property `required: true` or
`required: false`. A required property absent on the selected page or block
makes the whole operation `unsupported`; an absent optional property is
omitted. A consumer property missing from the producer profile, or declared
with a different type or cardinality, rejects session admission. A host-hidden
or non-public property can never appear in the producer profile. Properties
present at the host but absent from the consumer profile are not requested and
are not exposed.

JSON `null`, raw maps or host entities, nested arrays, mixed-type arrays,
non-finite or lossy numbers, negative zero, invalid dates, invalid URLs,
unknown/custom types, malformed node references, and duplicate keys or values
are unsupported. If an eligible requested property cannot be represented, the
whole operation returns `unsupported` with an empty result. The producer never
drops, stringifies, or coerces that property to manufacture a pass.

## Fixed v1 limits

The following inclusive ceilings apply after UTF-8 encoding:

| Dimension | Ceiling |
| --- | ---: |
| Opaque identifier | 128 Unicode characters |
| Page title | 4,096 bytes |
| One block text | 16,384 bytes |
| Nodes in one subtree | 500 |
| Subtree depth, root included | 64 |
| Properties on one page or block | 64 |
| Properties across one result | 4,096 |
| Property key | 128 bytes |
| One scalar value or node-reference label | 4,096 bytes |
| Values in one many-valued property | 64 |
| Complete canonical operation result | 262,144 bytes |

These values reuse conservative, already exercised Plumber safety envelopes
for outline node count, block text, subtree depth, and bounded payload output.
They do not prove that a Logseq host can deliver them.

Canonical JSON follows [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785).
All digests are lowercase hexadecimal SHA-256. A profile digest is computed
over the canonical UTF-8 profile object after omitting its own
`profile_sha256` member. A request object carries `request_sha256` as its own
top-level member. To compute it, omit that member from the nested request
object, place the remaining object in `payload`, and hash the canonical UTF-8
bytes of this wrapper:

```json
{
  "contract_id": "plumber.graph.payload.read/v1",
  "schema_version": 1,
  "kind": "request",
  "operation": "<capability>",
  "payload": {}
}
```

A result object likewise carries `result_sha256` as its own top-level member.
Its digest uses the same wrapper with `kind: "result"` and the remaining
complete operation-result object in `payload` after that member is omitted.
After hashing, insert the digest into the corresponding nested object without
changing any other member. The complete-result ceiling is measured over the
canonical result-wrapper bytes before `result_sha256` is inserted. The empty
object above is replaced by the complete nested request or result object.
Boundary values pass. Counting and digest verification occur before returning
content to the consumer.

A request with limits that differ from its hash-bound profile is `rejected`.
Host data that exceeds an accepted limit is `unsupported`. Neither outcome
returns a partial payload. There is no implicit limit negotiation: the session
binds one exact effective limit set; producer maxima must cover it and consumer
ceilings must equal it.

## Result bindings and provenance

Every runtime operation result binds:

- contract ID and schema version;
- exact producer and consumer profile IDs and SHA-256 hashes;
- graph ID, active session ID, and source revision;
- official host release, asset identity and artifact digest;
- embedded host revision and selected transport identity;
- exact Plumber commit and tree;
- canonical request digest and canonical result digest.

The shared graph, session, source, artifact, transport, and Plumber bindings
must be byte-identical across related identity, page, and subtree runtime
records. A separate qualification record binds those runtime records to the
synthetic-fixture ID and digest, evidence-profile ID, pre/post state digests,
and private evidence location. Ordinary runtime results do not claim a fixture
or qualification context.

For a qualification set, the separate qualification record references the
three runtime-result digests and asserts that their shared graph, session,
source, artifact, transport, and Plumber bindings are byte-identical. The
qualification record alone carries fixture and evidence-profile bindings. A
session that is unknown, closed, expired, foreign to the graph, bound to
another source revision, or bound to different profiles is rejected. A source
revision change never triggers retry, fallback, or source mixing.

## Outcomes

The operation outcome vocabulary is:

- `pass`: one complete, valid, bound result;
- `rejected`: the request, session, entitlement, profile, or declared limit set
  is invalid;
- `unsupported`: the selected source cannot represent the requested capability
  completely under the accepted contract;
- `error`: the selected adapter or host failed without a safe semantic result.

Every non-pass outcome has an empty result. Reasons use bounded, stable reason
codes and do not include host payload, paths, credentials, or raw errors.

## Consumer intent and runtime entitlement

A future `plumber.consumer.package/v1` binding may record static intent for an
exact payload schema, consumer profile hash, capabilities, property allowlist,
and effective limits. That package remains static-only and unqualified. It is
neither permission nor evidence that a producer, consumer, host, or transport
works.

Runtime delivery additionally requires explicit operator admission, an active
session, exact profile compatibility, and the requested declared capability.
The default is deny. Matryca Trama and Matryca Brain remain consumers through
Plumber contracts only; neither receives direct Logseq or Parser authority.

## Privacy and evidence publication

An explicitly entitled local runtime consumer may receive bounded graph
content. That content remains private graph data.

Committed fixtures contain only purpose-written synthetic text. Public
evidence may publish contract IDs, classifications, counts, non-sensitive
bindings, and hashes of synthetic artifacts. It must not publish user content,
raw host output, credentials, local paths, private logs, or public hashes
derived from private content. Private raw qualification evidence stays outside
Git and is retained under its separate evidence policy.

This redaction policy does not weaken runtime validation: private evidence must
still prove exact content, properties, order, completeness, and pre/post state
before a sanitized result can support a capability decision.

## Rejected alternatives

- **Widen `plumber.graph.read/v1`:** rejected because it would change the
  established content-free contract and couple identity to payload exposure.
- **Treat a page as concatenated Markdown:** rejected because it invents a
  representation that is not the DB page model and can lose block identity,
  properties, and order.
- **Expose raw Logseq objects or arbitrary properties:** rejected because it
  leaks host internals, weakens privacy, and prevents a stable consumer contract.
- **Drop unsupported properties and return partial success:** rejected because
  consumers could mistake incomplete evidence for a complete read.
- **Negotiate limits dynamically:** rejected because an implicit intersection
  is difficult to attest and can change behavior without changing a profile.
- **Publish content-derived hashes as public evidence:** rejected because small
  or predictable private values can be susceptible to guessing attacks.

## Consequences and next gate

The later static contract and TCK have precise behavior to enforce, but this
decision alone makes no capability available. Existing graph-read, topology,
consumer-package, Parser, Shadow, UI, CLI, MCP, and release behavior remains
unchanged.

The next programme boundary is a new bundled-CLI artifact dossier and admission
attempt. Only a separately qualified official host may justify writing the
static payload artifact and later runtime layers. A terminal
`capability_no_go` or `upstream_blocked` result remains valid progress and does
not authorize fallback within the same attempt.
