# OG graph gateway: alpha.3 invocation reference

Status: source-bound operator reference, verified 2026-10-24. This document
describes existing behavior; it does not add a command, contract, dependency,
consumer permission or supported user-graph capability.

## Authority and scope

The command and error mapping below come from
[`bootstrap.py` at the alpha.3 producer source](https://github.com/MarcoPorcellato/matryca-plumber/blob/8c30f70e217722e719c5aedc322219ebccb87e68/matryca_plumber/graph_gateway/bootstrap.py).
The producer is `2.1.0a3` at
`8c30f70e217722e719c5aedc322219ebccb87e68`; a later verifier checkout is not a
replacement producer. Consult the [immutable public handoff](../quality/OG_OPERATIONAL_V1_ALPHA3_PUBLIC_HANDOFF.md)
for original wheel, dependency, descriptor, provenance and qualification
bindings. A source checkout or this guide is not an installed-package receipt.

Trama's [owner decision](https://github.com/MarcoPorcellato/matryca-trama/issues/2#issuecomment-6383824647)
admits only the exact original-wheel synthetic tuple on Linux x86_64 and macOS
arm64, CPython 3.12.14, with Parser 1.9.0 in the separate producer environment.
It does not authorize a user graph. Packaged proposed, static-only-unqualified,
unqualified and planned labels remain unchanged. No payload, native DB, general
Logseq-version range, OS network-isolation or stable-support claim follows.

## Explicit invocation

Select the absolute Python executable inside the separately authenticated
producer virtual environment. Preserve that executable path: resolving the
venv executable symlink and invoking its base interpreter would change the
environment. Verify executable identity separately. Do not import Plumber or
Parser into the consumer process.

The graph-free command accepts no additional arguments:

```text
/absolute/producer-venv/bin/python -I -B -m matryca_plumber.graph_gateway describe
```

The snapshot command accepts exactly the two distinct, nonempty flags below;
the descriptor expectation is a lowercase 64-character SHA-256:

```text
/absolute/producer-venv/bin/python -I -B -m matryca_plumber.graph_gateway snapshot --graph-root <canonical-authenticated-synthetic-root> --expect-descriptor-sha256 bcc6ac607706e934e5df4e044802aa74c7d7455e7711220df116080f1ab0cc70
```

Establish the allowed synthetic-root boundary before reading a directory or
starting the producer. Canonicalize an admitted root in the consumer before
invocation; the producer rejects symlink roots and differing lexical/resolved
interpretations. This is not permission to
inspect an arbitrary path and decide afterward whether its digest matches.

Use explicit arguments, no shell, closed stdin, a fresh selected environment
and the reviewed consumer process boundary. Enforce stdout/stderr bounds while
reading, the execution deadline and the shared finalization deadline. A zero
exit is insufficient: authenticate and validate the owner resources and all
profile, graph/session/revision, completeness and cleanup bindings. Process
cleanup still requires reaping, ESRCH within the deadline and every stream,
reader and selector gate passing. The producer audit hook is not an OS sandbox.

## Output and exit status

Exit `0` writes one JSON document to stdout. Diagnostics or extra output do not
become graph data. Errors write a bounded JSON object of the form
`{"error":"source_rejected"}` plus newline to stderr. Match both the error
code and exit status; a nonzero exit alone is not an accepted negative control.
Do not echo raw output into logs or user-facing exceptions.

| Error code | Exit status | Meaning | Retry semantics |
| --- | --- | --- | --- |
| `usage` | `2` | Invocation arguments rejected. | Unspecified by this producer interface. |
| `expectation_mismatch` | `3` | Expected descriptor does not match the selected profile. | Unspecified by this producer interface. |
| `source_rejected` | `4` | Source/root cannot satisfy the selected read boundary. | Non-retryable in the accepted consumer boundary. |
| `bounds_exceeded` | `5` | A declared finite source, topology or output bound was exceeded. | Unspecified by this producer interface. |
| `source_changed` | `6` | A source change was observed during capture verification. | Unspecified by this producer interface. |
| `unsupported_platform` | `7` | Platform or Python minor version refused. | Unspecified by this producer interface. |
| `unsupported_dependency` | `8` | Selected dependency identity/version refused. | Unspecified by this producer interface. |
| `audit_hook_unavailable` | `9` | The startup audit-hook self-check did not establish registration. | Unspecified by this producer interface. |
| `internal` | `70` | Internal failure; no successful topology is established. | Unspecified by this producer interface. |

Only exit `4` has the explicit non-retryable consumer-policy statement above;
the other codes are not an automatic retry authorization. Trama may separately
choose a stricter non-retryable policy for all client errors. Neither this table
nor such a policy rewrites producer wire semantics.

The drift check reads `ERROR_EXITS` as source syntax without importing or
invoking the producer. Future changes require an explicit reference update;
they must not silently reinterpret the immutable alpha.3 evidence.

## Further design remains separate

The admitted topology is content-free and complete-only. Larger graph capacity,
page titles, text/properties, pagination, real-vault isolation and a changed
dependency or runtime tuple need their own owner-defined capability, release,
qualification and consumer decision. Keep topology content-free; do not infer
titles or text from opaque identifiers.
