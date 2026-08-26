---
type: Decision
title: Source static-analysis adoption baseline
description: Evidence-bounded adoption record for a fast source security gate, reviewed suppressions, staged assertion hardening, and hosted-compute limits.
status: stable
classification: active
audience: [maintainer, contributor]
owner: quality
last_verified: 2026-08-25
stale_after: 2027-02-21
---

# Source static-analysis adoption baseline

## Decision

Matryca Plumber adds a fast, source-only security static-analysis gate to the
existing `make check` and `make ci` contracts. The gate uses the repository's
already pinned Python analysis stack, runs without network or container access,
and does not create another hosted workflow job.

The first baseline excludes runtime-assertion findings. Those assertions require
separate behavior-preserving hardening and regression review before they can
become blocking. The exclusion is therefore an explicit temporary boundary, not
a claim that assertions are safe in optimized Python execution.

## Baseline evidence

The source scan began with 18 findings:

| Family | Count | Initial disposition |
| --- | ---: | --- |
| Runtime assertions | 9 | Deferred to a separate reviewed change. |
| Fixed local executable paths | 3 | Accepted with line-bound rationale; no shell or graph/request value enters the command. |
| URL opening | 2 | Accepted where the URL is fixed locally or validated by the inference URL policy. |
| All-interface literal | 2 | Accepted false positives: both occurrences compare a host value and do not bind a socket. |
| Subprocess input | 1 | Accepted: exact current interpreter and module, framed input, no shell. |
| Dynamic SQL shape | 1 | Accepted: interpolation creates only parameter placeholders; values remain separately bound. |

Every accepted finding has a narrow source annotation next to the relevant
operation. Repository-wide or file-wide suppressions are not used.

## Gate contract

- Canonical command: `make security-check`.
- Scope: production Python under `src/`.
- Placement: existing local and hosted aggregate gates.
- Network: none.
- Containers and heavy local admission: none.
- Hosted compute: no additional job; only the sub-second source scan is added to
  the existing aggregate job.

Passing this gate proves only that the exact checked source satisfies the
recorded static policy and reviewed suppressions. It does not prove runtime
behavior, dependency freshness, absence of vulnerabilities, platform parity, or
release qualification.

## Promotion criteria

The runtime-assertion exclusion may be removed only when:

1. each production assertion is classified as type narrowing, an internal
   invariant, or user-reachable validation;
2. user-reachable and safety-relevant invariants fail explicitly under optimized
   Python execution;
3. every behavior change has a red-green regression test;
4. focused tests, strict typing, the full source security gate, and the complete
   repository gate pass on the exact candidate commit;
5. the change-impact review reports no unresolved high-risk caller.

## Future pilots

Workflow-security, workflow-correctness, dependency-classification, and
vulnerability-advisory analyzers remain separate measured pilots. They must not
be added to tracked CI or public documentation until their versions, provenance,
false-positive rate, runtime, local/offline behavior, hosted-minute effect, and
compatibility with the repository's vendor-neutral tooling policy are reviewed.

Any pilot starts informationally. Promotion to a blocking gate requires a
separate decision and must not silently enlarge the heavy local qualification
matrix.
